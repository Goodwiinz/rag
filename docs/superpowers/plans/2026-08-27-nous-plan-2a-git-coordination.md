# NOUS Git coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Git-backed coordination the remote-authoritative board after cutover, with orphan bootstrap, shallow CAS snapshots, claim fencing, expiry/compensation, mode enforcement, retention GC, and a guarded subprocess boundary.

**Architecture:** GitIO is the only production module allowed to invoke git or gh; it accepts an injectable runner and rejects force/deletion pushes before execution. GitBackend reads and writes complete coordination snapshots on an orphan nous-coordination branch through unique local temporary refs and ordinary fast-forward pushes. CombinedBackend composes GitBackend with Plan 0’s local flock backend, acquiring remote first and local second and compensating failed local acquisition.

**Tech Stack:** Python 3.11+ standard library (subprocess, dataclasses, json, pathlib, os, re, secrets, time, random, typing, tempfile) plus pytest and local temporary Git repositories. No PyYAML and no application/backend dependencies are available in the isolated script-test gate.

**Spec:** docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md

> **Protocol addendum (2026-08-29):** The schema-2 Vercel deployment guard in
> `docs/superpowers/specs/2026-08-29-nous-vercel-deployment-exclusion-design.md`
> supersedes this plan's claims/runs-only tree assertions. The original steps
> remain historical implementation evidence for schema 1.

## Global Constraints

- Depends on Plan 1 and consumes its ReceiptStore, PreflightResult, and CLI error mapping without changing their meanings.
- All new code under scripts/nous/ remains stdlib-only. Git and gh subprocesses go through GitIO; no shell=True, shell strings, force flags, deletion flags, or remote-derived values interpolated into commands.
- During the compatibility window, the orphan `nous-coordination` branch may
  remain schema 1 (`claims.json` and `runs/<run-id>.json`) for legacy read
  compatibility; supported mutations normalize their child to schema 2.
  Current schema-2 writes contain `claims.json`, the repository-owned
  `vercel.json` deployment guard, and `runs/<run-id>.json`; every update is a
  complete snapshot child commit.
- Bootstrap uses one ordinary push of the orphan root to an absent ref; it does not call GitHub REST createRef, upload to a temporary remote ref, merge histories, or retry the losing commit object.
- Normal fetches use depth 1 and unique refs/nous/tmp/<run-id>-<nonce>; the plus refspec is permitted only for that private local tracking ref and never for push.
- CAS retries at most five attempts with min(30, 1.5**attempt) * uniform(0.5, 1.5) jitter; transport exhaustion is exit 3, visible logical conflict exhaustion is exit 2.
- Default new-CLI claim TTL is 10,800 seconds; renewal is only under 45 minutes or immediately before a long gate; expiry is final and pruning uses a 120-second skew allowance.
- Remote run records are created in the same claim commit, never in preflight. Every mutation of an existing run presents the exact claim_id fencing token. After the claim establishes the run, each local receipt state event is durably appended before its remote CAS; a failed CAS calls ReceiptStore.mark_remote_lagging() and blocks further state work until reconciliation repairs it.
- Remote-required never falls back to local-only. The local board is a same-host mutex; direct legacy mutations are blocked by .remote-required after cutover, while CombinedBackend calls local backend methods directly.
- No production credentials, stdout, tracebacks, prompts, or arbitrary PR text enter remote JSON. Unknown/oversized/control/secret-shaped fields reject writes and quarantine reads.
- Every task ends with its own red/green test cycle and scoped commit. Do not implement GitHub publication/reconciliation; that is Plan 2b.

## File map and cross-plan interfaces

| Path | Ownership in this plan |
| --- | --- |
| scripts/nous/gitio.py | Command runner, git plumbing, GitHub API transport helpers, no-force runtime guard, dedicated committer env. |
| scripts/nous/backend_git.py | Remote snapshot schema serialization, bootstrap, shallow CAS, expiry/pruning, claim fencing, retention GC, mode checks. |
| scripts/nous/coordination.py | Add CombinedBackend and remote/local synchronization hooks while retaining Plan 0 models/protocol. |
| scripts/nous/backend_local.py | Add cutover sentinel read/write and direct-legacy mutation guard; retain Plan 0 file format. |
| scripts/nous/preflight.py | Add environment config, backend selection, GitIO-backed probe adapter, and remote-required read labels. |
| scripts/nous_run.py | Wire config/backend selection and the Plan 2a remote commands (claim/renew/status/list/gc); leave publish/merge/reconcile/resume to Plan 2b. |
| docs/engineering/nous-loop.md | Add canonical Git coordination, remote-required authority, sentinel, and rollout/rollback instructions without runtime-specific language. |
| tests/unit/scripts/test_nous_gitio.py | Runner injection and force/shell/committer contracts. |
| tests/unit/scripts/test_nous_git_backend.py | Bare-repo bootstrap/CAS/race/expiry/fencing/retention tests. |
| tests/unit/scripts/test_nous_remote_selection.py | CombinedBackend order, compensation, mode and sentinel behavior. |
| tests/unit/scripts/test_nous_coordination_contract.py | Workflow trigger scanner and static no-force contracts. |
| tests/unit/scripts/test_nous_run_cli.py | Extend Plan 1 CLI tests for remote-required selection and stable exit codes. |

Plan 2b consumes GitIO.gh_json(), GitBackend.get_run()/list()/finalize(), CombinedBackend.release()/renew(), and PreflightResult mode/config fields. Plan 3 does not depend on this plan. Plan 4 consumes GitBackend.gc() through the CLI but does not alter CAS semantics.

### Task 1: Build the guarded GitIO subprocess boundary

**Files:**
- Create: scripts/nous/gitio.py
- Create: tests/unit/scripts/test_nous_gitio.py

**Interfaces:**
- Produces CommandResult(returncode: int, stdout: str, stderr: str) and Runner protocol run(argv: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None, input_text: str | None = None) -> CommandResult.
- Produces SubprocessRunner.run with subprocess.run(list(argv), cwd=cwd, env=env, input=input_text, shell=False, capture_output=True, text=True, check=False); it maps OSError to BackendUnavailable without printing command output.
- Produces NonFastForward(Conflict), RemoteRefMissing(ValidationError), TransportFailure(BackendUnavailable), GitHubPermissionDenied(ValidationError), and CommitIdentity(committer_name: str, committer_email: str). Push classification is based on recorded `git push --porcelain` status, never echoed remote text: fetch-first/non-fast-forward rejection maps to NonFastForward; every other nonzero push result maps to TransportFailure.
- Produces GitIO(repo_root: Path, *, runner: Runner | None = None, sleep: Callable[[float], None] = time.sleep, jitter: Callable[[float, float], float] = random.uniform) with run_git(args: Sequence[str], *, check: bool = True, env: Mapping[str, str] | None = None, input_text: str | None = None) -> CommandResult, run_gh(args: Sequence[str], *, check: bool = True, input_text: str | None = None) -> CommandResult, gh_json(method: str, endpoint: str, payload: Mapping[str, object] | None = None, *, allow_not_found: bool = False) -> object | None, check_branch_format(branch: str) -> bool, fetch_branch(remote: str, branch: str, temp_ref: str, *, allow_missing: bool = False) -> str | None, fetch_coordination(remote: str, branch: str, temp_ref: str) -> str, commit_identity(commit: str) -> CommitIdentity, list_tree(commit: str) -> tuple[str, ...], cat_file(commit: str, path: str) -> bytes, delete_local_ref(temp_ref: str) -> None, and push_fast_forward(remote: str, commit: str, branch: str) -> None.
- Produces validate_push_args(args: Sequence[str]) -> None. A push containing --force, --force-with-lease, -f, --delete, or a refspec beginning with + raises ValidationError. A fetch may use + only when the destination starts refs/nous/tmp/; any other plus refspec is rejected.
- Produces commit_snapshot(files: Mapping[str, bytes], *, parent: str | None, message: str) -> str using hash-object -w, recursive bottom-up mktree calls, and commit-tree. Nested paths such as runs/<run-id>.json are represented by real subtree objects, never passed to mktree as a slash-containing entry. Each plumbing call receives GIT_AUTHOR_NAME=NOUS Coordination, GIT_AUTHOR_EMAIL=nous-coordination@invalid, GIT_COMMITTER_NAME=NOUS Coordination, and GIT_COMMITTER_EMAIL=nous-coordination@invalid in a per-call environment copy.

- [ ] **Step 1: Add failing runner and force-guard tests**

Use a fake Runner that records argv/env and returns configured results:

~~~python
def test_push_rejects_every_force_or_delete_form_before_runner(fake_runner):
    io = GitIO(Path("/repo"), runner=fake_runner)
    for args in (
        ("push", "origin", "--force", "x:refs/heads/y"),
        ("push", "origin", "--force-with-lease", "x:refs/heads/y"),
        ("push", "origin", "-f", "x:refs/heads/y"),
        ("push", "origin", "--delete", "refs/heads/y"),
        ("push", "origin", "+x:refs/heads/y"),
    ):
        with pytest.raises(ValidationError):
            io.run_git(args)
    assert fake_runner.calls == []


def test_private_fetch_plus_refspec_is_the_only_allowed_plus(fake_runner):
    io = GitIO(Path("/repo"), runner=fake_runner)
    io.fetch_coordination("origin", "nous-coordination",
                           "refs/nous/tmp/20260827T040000Z-agent-9f3a1c-abcdef123456")
    assert fake_runner.calls[0][0][:3] == ["git", "fetch", "--depth"]


def test_commit_uses_dedicated_identity(fake_runner):
    io = GitIO(Path("/repo"), runner=fake_runner)
    io.commit_snapshot({"claims.json": b'{"claims": []}\n'}, parent=None, message="bootstrap")
    env = fake_runner.calls[-1][1]
    assert env["GIT_COMMITTER_EMAIL"] == "nous-coordination@invalid"
~~~

- [ ] **Step 2: Run GitIO tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_gitio.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because scripts.nous.gitio and GitIO do not exist.

- [ ] **Step 3: Implement argument-list execution and plumbing helpers**

Implement SubprocessRunner with an argument list and shell=False. GitIO.run_git prepends git and run_gh prepends gh api only through the same runner. Use `git push --porcelain` and classify only its stable rejection categories: a fetch-first/non-fast-forward rejection raises NonFastForward; any other nonzero result raises TransportFailure with a generic operation label rather than stdout/stderr. `gh_json` serializes a payload to `input_text` and uses `gh api --input -` only when a payload is present, then parses JSON from stdout; response-shape validation remains the caller's responsibility. It runs gh with check=False and extracts only a trailing numeric `(HTTP NNN)` status from an error without retaining/echoing the surrounding text: allow_not_found plus 404 returns None, 401/403 raises GitHubPermissionDenied, 408/429/5xx raises BackendUnavailable, other recognized 4xx raises ValidationError, and an unclassified failure raises BackendUnavailable.

Implement validate_push_args by inspecting tokens after the command name. A plus refspec is rejected for push but allowed for the exact local temporary fetch destination. Do not include any force spelling in a production push command. `check_branch_format` first applies the pure schema validator (so a leading dash never reaches Git), then calls `git check-ref-format --branch <validated-branch>` with check=False and returns whether it succeeded; remote writes pass this callback into validate_branch_syntax. fetch_branch constructs the exact depth-one refspec from a validated configured branch to a caller-provided unique refs/nous/tmp/... ref, maps only Git's known "couldn't find remote ref" failure to RemoteRefMissing/None when allow_missing, and otherwise raises BackendUnavailable; fetch_coordination calls it with allow_missing=False and returns the validated SHA. `commit_identity` uses a fixed `git show -s --format=%cn%x00%ce` format and parses exactly two control-delimited fields; it never echoes unexpected identity text. `list_tree` uses `git ls-tree -r --name-only -z` and validates every decoded path before returning it; `cat_file` reads only one of those validated paths. `delete_local_ref` accepts only refs/nous/tmp/... and uses update-ref -d, never a remote push deletion. `commit_snapshot` writes blobs, builds a validated path trie, calls mktree bottom-up with sorted direct children through `input_text`, and calls commit-tree with -p only when parent is not None; it returns the validated 40-hex SHA.

- [ ] **Step 4: Run GitIO tests and a static force scan**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_gitio.py -q -p no:cacheprovider --no-cov
python3 - <<'PY'
from pathlib import Path
text = Path("scripts/nous/gitio.py").read_text(encoding="utf-8")
assert "shell=True" not in text
assert "git push --force" not in text
print("gitio static guard ok")
PY
~~~

Expected: PASS for all GitIO tests and the command prints gitio static guard ok.

- [ ] **Step 5: Commit GitIO**

~~~bash
git add scripts/nous/gitio.py tests/unit/scripts/test_nous_gitio.py
git commit -m "feat(nous): add guarded git and github transport"
~~~

### Task 2: Implement orphan bootstrap and full-snapshot CAS updates

**Files:**
- Create: scripts/nous/backend_git.py
- Create: tests/unit/scripts/test_nous_git_backend.py

**Interfaces:**
- Consumes GitIO, CommandResult, and validate_push_args from Task 1; consumes Claim, Candidate, Milestone, Blocker, RunProjection, CoordinationBackend, Conflict, ClaimLost, BackendUnavailable, ValidationError, ClaimRequest, and schema validators from Plan 0.
- Produces GitBackendConfig(remote: str, branch: str, mode: str, machine_id: str, repo_slug: str | None, ttl_seconds: int = 10800, skew_seconds: int = 120, max_attempts: int = 5).
- Produces CoordinationSnapshot(mode: str, updated_at: str, claims: tuple[Claim, ...], runs: Mapping[str, RunProjection]), ForeignMetadata(ValidationError), and GitBackend(config: GitBackendConfig, io: GitIO, *, clock: Callable[[], datetime] | None = None).
- GitBackend methods satisfy the Plan 0 remote protocol exactly: claim(*, run_id: str, agent: str, machine_id: str, branch: str, area: str, files: Sequence[str], candidate: Candidate | None, pr: int | None, ttl_seconds: int, claim_id: str | None = None, base_sha: str | None = None, evidence_head_sha: str | None = None) -> Claim; assert_claim(*, run_id: str, claim_id: str) -> Claim; renew(*, run_id: str, claim_id: str, ttl_seconds: int) -> Claim; release(*, run_id: str, claim_id: str, reason: str, remove_run: bool = False) -> None; list() -> list[Claim]; check(*, area: str, files: Sequence[str]) -> list[Claim]; put_run(projection: RunProjection, *, claim_id: str) -> None; get_run(run_id: str) -> RunProjection; list_runs() -> tuple[RunProjection, ...]; finalize(projection: RunProjection, *, claim_id: str, release_claim: bool) -> None; finalize_orphan(projection: RunProjection, *, expected_claim_id: str, expected_updated_at: str) -> None. assert_claim freshly fetches and validates the live token/expiry without committing; finalize_orphan is the reconciliation-only no-active-claim path with last-token plus updated-at fencing.
- Produces bootstrap(*, mode: str | None = None) -> str, prune_expired(*, now: datetime | None = None) -> tuple[str, ...], gc(*, now: datetime | None = None) -> tuple[str, ...], and assert_mode(remote_mode: str) -> None. bootstrap returns the winning/fetched tip and has no createRef path; prune_expired uses the 120-second skew rule in one ordinary CAS update.
- Produces serialize_claims(snapshot: CoordinationSnapshot) -> bytes, serialize_run(projection: RunProjection) -> bytes, decode_snapshot(commit: str) -> CoordinationSnapshot, and cas_update(operation: Callable[[CoordinationSnapshot], tuple[CoordinationSnapshot, object]]) -> object.
- Every CAS operation creates a unique temp ref with run ID plus 12-hex nonce, verifies the fetched tip's committer is exactly NOUS Coordination <nous-coordination@invalid>, reads all tree files from that commit, validates unknown/oversized/secret/control/path fields on read, builds a child commit with the complete intended claims and runs snapshot, pushes plain commit:refs/heads/nous-coordination, and deletes the local temp ref in finally. A foreign identity raises ForeignMetadata before the operation callback; reads report it and mutations never auto-repair it.

- [ ] **Step 1: Add failing bare-repository bootstrap and CAS tests**

Create a local bare repository and two clones with a helper that configures a disposable Git identity. Test the initial root, files, parent relationship, and bootstrap race:

~~~python
def test_bootstrap_creates_orphan_with_only_claims_json(two_clones):
    backend = two_clones[0]
    tip = backend.bootstrap(mode="remote-required")
    assert run_git(backend.repo, "rev-list", "--max-parents=0", tip).stdout.strip() == tip
    assert run_git(backend.repo, "ls-tree", "-r", "--name-only", tip).stdout.splitlines() == ["claims.json"]


def test_interleaved_claim_cas_loser_refetches_and_conflicts(two_backends):
    left, right = two_backends
    left.bootstrap(mode="remote-required")
    first = left.claim(**claim_kwargs(area="same"))
    with pytest.raises(Conflict):
        right.claim(**claim_kwargs(area="same"))
    assert first.claim_id and len(first.claim_id) == 14
    assert len(right.list()) == 1


def test_bootstrap_race_returns_the_single_winning_root(two_backends):
    tips = run_concurrently(
        lambda backend: backend.bootstrap(mode="remote-required"), two_backends
    )
    assert len(set(tips)) == 1
    assert remote_root_count(two_backends[0]) == 1


def test_foreign_tip_is_reported_and_never_repaired(backend, foreign_tip):
    with pytest.raises(ForeignMetadata):
        backend.list()
    assert remote_tip(backend) == foreign_tip
~~~

- [ ] **Step 2: Run GitBackend tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_git_backend.py -q -k 'bootstrap or cas' -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because GitBackend, snapshot serialization, and the temporary-ref CAS loop do not exist.

- [ ] **Step 3: Implement remote JSON and orphan bootstrap**

Serialize claims with exact whitelisted fields: schema, mode, updated_at, and active claims. Serialize each run projection with exact fields from the Plan 0 dataclass, including validated files/candidate needed for later re-claim, at most 40 Milestone entries, and the top-level milestones_truncated boolean. When appending beyond 40, drop oldest remote entries and set that flag; never invent a marker that violates the Milestone schema. Sort keys and use UTF-8 JSON with a trailing newline. Validate byte size before writing. Before decoding any fetched tip, compare GitIO.commit_identity to the exact dedicated identity; a mismatch raises ForeignMetadata containing only the validated tip SHA and operation label. Use GitIO.list_tree to enumerate the snapshot, then deserialize every listed file through git cat-file; reject a filename whose embedded run_id differs, reject unknown files, and treat invalid peer data as corrupt/invalid rather than repairing it.

For bootstrap, create claims.json with schema=1, configured mode, empty claims, and current UTC timestamp; call GitIO.commit_snapshot with parent=None and message "nous coordination bootstrap"; call push_fast_forward with the plain refspec. If the push reports NonFastForward because the remote ref now exists, leave the losing commit unreachable (it may remain in the local object database until normal Git GC), fetch the winning branch, assert its mode, and return its tip; the caller must re-derive its intended operation rather than retry the losing commit.

Implement cas_update to fetch into refs/nous/tmp/<safe-run-id>-<nonce> with depth 1, decode the snapshot, call operation(snapshot) to re-derive conflict/fencing/expiry, build a full child snapshot, push fast-forward, and delete the temp ref in finally. Retry only non-fast-forward and transport errors up to five times with the exact jitter formula. A visible conflict returned by operation is not retried as a stale commit. Do not merge fetched histories.

- [ ] **Step 4: Implement claim, run creation, and fencing**

claim validates every scalar and candidate, validates branch through validate_branch_syntax(..., checker=io.check_branch_format), asserts configured mode against the board header, prunes only claims with expires_at earlier than now minus 120 seconds, and checks case-insensitive area or shared-file overlap. Add `claim_id: str | None = None` to ClaimRequest and the backend claim signature. A brand-new run requires claim_id=None. An idempotent retry of an active claim requires the exact token and matching run_id, agent, machine_id, and branch. Re-acquiring an expired nonterminal run requires the prior token from its RunProjection; the winning CAS writes a newly generated token into both the claim and projection, so every concurrent or stale presentation of the old token then loses fencing. Another machine/agent/branch or a missing/mismatched prior token is Conflict/ClaimLost before a child commit is built. For a new or valid re-acquired claim generate claim_id as c- plus secrets.token_hex(6), expires_at=now+ttl, and create or update the matching RunProjection in the same snapshot commit with state claimed, outcome/blocker/PR null, base_sha and evidence_head_sha taken from the optional claim arguments (both are required and equal to the fetched base when remote CLI first claims), and the claimed/reclaimed milestone. Plan 2a’s CLI obtains the base SHA from its preflight result and passes base_sha=preflight.base_sha and evidence_head_sha=preflight.base_sha to this API; these are internal arguments, not new user-facing flags, and no preflight path creates a remote run.

assert_claim performs a fresh shallow fetch and exact live-token/expiry check without constructing a commit. put_run, renew, release, and finalize call cas_update and compare the presented claim_id to the active claim before constructing any child commit. A mismatch, missing claim, or expired claim raises ClaimLost and never retries stale intent. release removes the active claim and, when remove_run is true, removes the just-created run; finalize writes the terminal projection and optionally removes the claim in the same snapshot. finalize_orphan is callable only by the reconciliation service: its CAS requires that no active claim with that run_id exists, the stored projection claim_id equals expected_claim_id, updated_at equals expected_updated_at, and the new projection sets an allowed terminal outcome; any mismatch raises ClaimLost and the operation is re-derived. It never deletes a different active claim. check returns all live overlaps without mutating the board; list returns active claims only.

- [ ] **Step 5: Run the full GitBackend focused tests**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_git_backend.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for orphan root, exact files, bootstrap race re-derivation, full-snapshot parentage, unique temporary refs, non-fast-forward retry, transport classification, claim/run atomicity, overlap, and claim-id fencing.

- [ ] **Step 6: Commit bootstrap and CAS**

~~~bash
git add scripts/nous/backend_git.py tests/unit/scripts/test_nous_git_backend.py
git commit -m "feat(nous): add orphan coordination branch and cas snapshots"
~~~

### Task 3: Add expiry, renewal, retention GC, and remote/local composition

**Files:**
- Modify: scripts/nous/backend_git.py
- Modify: scripts/nous/coordination.py
- Modify: scripts/nous/backend_local.py
- Create: tests/unit/scripts/test_nous_remote_selection.py

**Interfaces:**
- Consumes GitBackend and GitBackendConfig from Task 2; consumes LocalBackend/LocalMutex, acquire_remote_then_local, ClaimRequest, Claim, Conflict, ClaimLost, BackendUnavailable, ReceiptStore.mark_remote_lagging, and ReceiptStore.mark_remote_synced from Plans 0–1.
- Produces BoardView(remote: tuple[Claim, ...], local: tuple[Mapping[str, object], ...], conflicts: tuple[str, ...]) and CombinedBackend(remote: GitBackend, local: LocalMutex, *, on_compensation_pending: Callable[[Claim], None] | None = None) satisfying CoordinationBackend. Its claim(*, run_id: str, agent: str, machine_id: str, branch: str, area: str, files: Sequence[str], candidate: Candidate | None, pr: int | None, ttl_seconds: int, claim_id: str | None = None, base_sha: str | None = None, evidence_head_sha: str | None = None) -> Claim calls remote first, then local.claim_legacy with only area/files/branch/agent/pr/ttl; local conflict releases remote with remove_run=True. assert_claim, prune_expired, gc, and finalize_orphan delegate to the authoritative GitBackend (the latter may best-effort release the matching branch from this machine's LocalMutex after the remote orphan finalization, but never blocks the remote terminal record on absence of a local entry). Its release loads the fenced remote projection to recover the validated branch, calls local.release_legacy first, then remote.release; finalize with release_claim=True follows the same local-first order and then calls the remote single-CAS terminal finalize, while release_claim=False leaves the mutex held and only updates remote metadata. Its renew first renews remote, then calls local.heartbeat_legacy with the returned claim branch in the same invocation. No in-memory run-to-branch map is used, so restart cannot break renewal/release. Its remote-protocol list()/check() return the remote-side list, while view(*, area: str | None = None, files: Sequence[str] = ()) -> BoardView reads and labels remote claims and raw legacy mutex records separately.
- Produces claim_remaining(expires_at: str, *, now: datetime) -> timedelta, should_renew(expires_at: str, *, now: datetime, long_gate: bool) -> bool, and prunable(expires_at: str, *, now: datetime, skew_seconds: int = 120) -> bool.
- Produces legacy_mutations_allowed(bridge_dir: Path, *, mode: str) -> bool, write_remote_required_sentinel(bridge_dir: Path) -> Path, and has_remote_required_sentinel(bridge_dir: Path) -> bool. The sentinel is a zero-content .remote-required file created with mode 0o600; only direct legacy mutation commands consult it.
- Produces GitBackend.gc(*, now: datetime | None = None) -> tuple[str, ...], which removes runs whose terminal milestone timestamp is more than 30 days old via ordinary full-snapshot CAS and never rewrites history or touches active/nonterminal runs.

- [ ] **Step 1: Add failing expiry/composition/sentinel tests**

Use a fake clock, a fake remote CoordinationBackend, and a distinct branch-keyed fake LocalMutex:

~~~python
REQUEST = {
    "run_id": "20260827T040000Z-agent-9f3a1c",
    "agent": "agent", "machine_id": "linux", "branch": "fix/bug",
    "area": "bug", "files": ("x.py",), "candidate": None, "pr": None,
    "ttl_seconds": 10800, "base_sha": "23c3551a30ac5d230f68a01b76650c27144571f5",
    "evidence_head_sha": "23c3551a30ac5d230f68a01b76650c27144571f5",
}


def test_renewal_is_only_under_45_minutes_or_long_gate():
    now = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)
    assert not should_renew("2026-08-27T06:00:01+00:00", now=now, long_gate=False)
    assert should_renew("2026-08-27T04:44:59+00:00", now=now, long_gate=False)
    assert should_renew("2026-08-27T06:00:01+00:00", now=now, long_gate=True)


def test_combined_acquires_remote_then_local_and_compensates():
    calls = []
    remote = RecordingBackend("remote", calls)
    local = RecordingLocalMutex(calls, claim_error=Conflict("same host"))
    with pytest.raises(Conflict):
        CombinedBackend(remote, local).claim(**REQUEST)
    assert calls[:2] == ["remote.claim", "local.claim_legacy"]
    assert calls[-1] == "remote.release(remove_run=True)"


def test_combined_view_labels_remote_and_local_claims():
    remote = RecordingBackend("remote", [])
    local = RecordingLocalMutex([])
    view = CombinedBackend(remote, local).view(area="bug", files=("x.py",))
    assert isinstance(view, BoardView)
    assert view.remote == tuple(remote.claims)
    assert view.local == tuple(local.legacy_claims)


def test_legacy_sentinel_blocks_only_direct_mutation(tmp_path):
    write_remote_required_sentinel(tmp_path)
    assert not legacy_mutations_allowed(tmp_path, mode="remote-required")
    assert has_remote_required_sentinel(tmp_path)
~~~

- [ ] **Step 2: Run focused tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_remote_selection.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL because renewal policy, CombinedBackend, sentinel helpers, and GC are absent.

- [ ] **Step 3: Implement expiry and claim loss**

Use timezone-aware datetime only. should_renew returns true when remaining time is strictly less than 45 minutes or long_gate is true; it returns false for an already expired timestamp. GitBackend.renew rejects expiry <= now, sets expires_at=now+ttl and renewed_at=now, and performs a CAS with exact claim_id. Peer pruning removes only claims for which now - 120 seconds > expires_at. Every edit/commit/push boundary begins with a fresh board fetch and exact claim-id/live-expiry check; a missing/pruned/expired claim raises ClaimLost and does not build or push code/metadata.

- [ ] **Step 4: Implement CombinedBackend and compensation-pending behavior**

Implement CombinedBackend.claim by constructing the Plan 0 ClaimRequest and invoking acquire_remote_then_local. `ClaimRequest.as_local_kwargs()` strips run_id, machine_id, claim_id, candidate, base/evidence SHAs before calling the branch-keyed LocalMutex, so the legacy file remains unchanged. If local acquisition fails, call remote.release with the exact token and remove_run=True. If that release is unavailable, invoke the supplied callback so ReceiptStore appends a compensation-pending event, and expose the condition as held-in-error to list/check callers until a later reconcile succeeds. CombinedBackend.release first fetches/validates the remote projection and token to obtain its branch, calls local.release_legacy(branch, reason), and then calls remote.release; it must not report free after remote failure. CombinedBackend.finalize performs that same local-first step only when release_claim=True, then delegates the terminal projection and release to the one remote CAS; a remote failure is held-in-error/reconciled, not reported free. With release_claim=False it retains the local mutex. CombinedBackend.renew uses the renewed remote Claim.branch for local.heartbeat_legacy and does not rely on process memory. check reads both sides and identifies which side supplied each conflict. CombinedBackend never passes through loop_bridge’s sentinel guard.

Add sentinel helpers that never modify the remote board. The Plan 2a CLI calls write_remote_required_sentinel only from the explicit cutover command after it has fetched and validated the remote-required board; bootstrap alone never writes it. Direct legacy claim/heartbeat/release/check commands refuse with exit 1 when the sentinel exists or NOUS_COORD_MODE=remote-required, while list remains observational and labels output local-only.

- [ ] **Step 5: Implement retention GC**

In GitBackend.gc, select only run projections with outcome in merged, ready-for-human, dry, or cancelled and a terminal milestone timestamp older than 30 days. Use one ordinary cas_update to remove those run files while preserving claims and all history. A run still referenced by an active claim is not removed. Return sorted IDs and let callers report them. Do not add a compaction or force-push method.

- [ ] **Step 6: Run expiry/composition tests and the unchanged bridge suite**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_remote_selection.py tests/unit/scripts/test_nous_git_backend.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/test_loop_bridge.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for 120-second skew, final expiry, under-45-minute renewal, long-gate renewal, stale-holder ClaimLost, remote-first/local-second compensation, held-in-error state, reverse release, local heartbeat, GC retention, and all unchanged legacy behavior.

- [ ] **Step 7: Commit expiry and composition**

~~~bash
git add scripts/nous/backend_git.py scripts/nous/coordination.py scripts/nous/backend_local.py tests/unit/scripts/test_nous_remote_selection.py
git commit -m "feat(nous): compose remote authority with local mutex"
~~~

### Task 4: Wire remote-required selection, CLI commands, and canonical workflow documentation

**Files:**
- Modify: scripts/nous/preflight.py
- Modify: scripts/nous_run.py
- Modify: scripts/loop_bridge.py
- Modify: docs/engineering/nous-loop.md
- Modify: tests/unit/scripts/test_nous_run_cli.py
- Modify: tests/unit/scripts/test_nous_loop_contract.py

**Interfaces:**
- Consumes GitIO, GitBackend, GitBackendConfig, CombinedBackend, LocalBackend, write_remote_required_sentinel, PreflightResult, Authorization, ReceiptStore, and Plan 1’s parser/error mapping.
- Produces RuntimeConfig(coord_mode: str, git_remote: str, github_repository: str | None, coordination_branch: str, loop_bridge_dir: Path | None, receipt_dir: Path, machine_id: str) and load_runtime_config(environ: Mapping[str, str], *, repo_root: Path) -> RuntimeConfig. Defaults are local, origin, nous-coordination, and ~/.nous-runs/<repo-basename>/; machine_id must be explicitly configured and pass validate_machine_id, never inferred from hostname.
- Produces SelectedBackend = LocalBackend | CombinedBackend and select_backend(*, config: RuntimeConfig, repo_root: Path, io: GitIO | None = None, local: LocalBackend | None = None) -> SelectedBackend. local selects the branch-keyed LocalBackend and the CLI uses its explicit legacy methods; remote-required selects CombinedBackend, which satisfies CoordinationBackend with GitBackend authoritative. Remote transport failure raises BackendUnavailable and never selects local-only. LocalBackend is never typed or treated as a remote-capable CoordinationBackend.
- Produces a GitIOBackedPreflight implementing Plan 1’s PreflightProbes: fetch_base() -> str, workspace() -> WorkspaceFacts, gates() -> GateInventory, backend_reachable() -> bool, and reconcile_prior_runs() -> tuple[str, ...]. Its workspace probe verifies a clean isolated worktree; its base probe fetches the configured remote/develop; its gate probe records available/unavailable/skipped gates without claiming skipped gates passed; reconcile_prior_runs only identifies runs needing the separate authorized reconcile command and performs no CAS.
- Extends the CLI so claim keeps the Plan 1 user-facing flags and passes the preflight base SHA internally to create the remote projection; no extra base-SHA flag is added. Adds operator-only bootstrap --mode remote-required and cutover --write-sentinel commands. bootstrap requires current-request coordinate authorization, constructs GitBackend directly without selecting/falling back to local, and creates or validates the remote board; cutover requires coordinate authorization, successfully fetches/validates a remote-required board, then writes only this machine's sentinel. In local mode claim/renew/release/check/list call the explicit LocalMutex methods (renew/release recover branch from the local receipt); gc reports unavailable because there is no remote projection store. In remote-required mode the same commands use CombinedBackend/GitBackend, and every mutation including gc requires coordinate. publish, verify-merge, reconcile, and resume remain explicit BackendUnavailable until Plan 2b. Remote check/list/status output labels remote board and local mutex separately.
- Updates docs/engineering/nous-loop.md with Git coordination authority, mode env vars, 3-hour TTL/renewal, claim-id fencing, remote-first/local-second compensation, shallow CAS, no-force rule, sentinel, remote-lagging, resume limitations, and rollout/rollback. Keep it runtime-neutral and preserve existing terminal outcomes and evidence gates.

- [ ] **Step 1: Add failing configuration, mode, and documentation tests**

Add tests for defaults, explicit machine identity, mode mismatch, no fallback, and canonical prose:

~~~python
def test_runtime_defaults_use_local_mode_and_repo_receipt_dir(tmp_path, monkeypatch):
    config = load_runtime_config({"NOUS_MACHINE_ID": "linux"}, repo_root=tmp_path / "rag")
    assert config.coord_mode == "local"
    assert config.git_remote == "origin"
    assert config.coordination_branch == "nous-coordination"
    assert config.receipt_dir == Path.home() / ".nous-runs" / "rag"


def test_machine_identity_is_required_and_never_inferred(tmp_path):
    with pytest.raises(ValidationError):
        load_runtime_config({}, repo_root=tmp_path / "rag")


def test_remote_backend_unavailable_is_not_replaced_by_local(fake_io, tmp_path):
    config = RuntimeConfig("remote-required", "origin", "o/r", "nous-coordination", tmp_path, tmp_path / "receipts", "linux")
    with pytest.raises(BackendUnavailable):
        select_backend(config=config, repo_root=tmp_path, io=fake_io)


def test_bootstrap_and_cutover_are_separate_authorized_steps(cli, tmp_path):
    auth = Authorization.from_names(("coordinate",))
    assert cli(["bootstrap", "--mode", "remote-required"], authorization=auth) == 0
    assert not has_remote_required_sentinel(tmp_path)
    assert cli(["cutover", "--write-sentinel"], authorization=auth) == 0
    assert has_remote_required_sentinel(tmp_path)


def test_canonical_doc_describes_remote_required_and_legacy_sentinel():
    text = Path("docs/engineering/nous-loop.md").read_text(encoding="utf-8")
    assert "remote-required" in text
    assert ".remote-required" in text
    assert "claim-id" in text
~~~

- [ ] **Step 2: Run focused tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_run_cli.py tests/unit/scripts/test_nous_loop_contract.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL because RuntimeConfig/select_backend/GitIO-backed probes and the canonical coordination section are not present.

- [ ] **Step 3: Implement runtime configuration and backend selection**

Parse only the named environment variables: NOUS_COORD_MODE (local or remote-required), NOUS_COORD_GIT_REMOTE (origin), NOUS_GITHUB_REPOSITORY (validated owner/repo or derived from the Git remote), NOUS_COORD_BRANCH (nous-coordination), LOOP_BRIDGE_DIR, NOUS_RECEIPT_DIR, and explicit NOUS_MACHINE_ID. Reject invalid mode, branch, repository, or machine identity with exit 4. Resolve the default receipt directory from the repository basename without reading a hostname. Construct LocalBackend with the configured bridge path and GitBackend with exact branch/mode/TTL/skew settings.

Modify the Plan 1 CLI dispatcher to call select_backend once per ordinary invocation and branch explicitly on LocalBackend versus CombinedBackend. Claim in remote-required mode must first pass preflight/action coordinate, then call CombinedBackend.claim so the remote claim and run projection are one commit before local acquisition. Record a compensation-pending receipt when needed. For reproduced/fixed/reviewed/locally_verified, advance requires coordinate, asserts the claim, appends the guarded local receipt event first, then calls put_run with the exact token; on CAS failure it marks remote-lagging and blocks further state work. Manually supplied published/hosted_verified/merged_verified targets remain rejected until Plan 2b derives those facts. `bootstrap` bypasses ordinary selection so an absent remote board can be created while both loops are stopped; it never writes the sentinel. `cutover --write-sentinel` re-fetches and validates the remote-required board before writing the sentinel on the current machine. Both require repeatable CLI `--authorize coordinate` (or an injected Authorization in tests). Direct legacy commands consult the sentinel and mode; list remains read-only and labels local-only.

- [ ] **Step 4: Implement GitIO-backed preflight and remote status labels**

The preflight adapter uses GitIO, not a second subprocess helper. fetch_base executes git fetch using RuntimeConfig.git_remote and develop, then resolves FETCH_HEAD; workspace verifies repository root, clean status, a distinct git-dir/common-dir worktree relationship, and absence of an unsafe superproject embedding; gates reports the fixed local CI command and every unavailable/skip separately; backend_reachable performs a depth-one coordination read and validates board mode; reconcile_prior_runs performs read-only detection of lagging/expired/orphaned runs and returns their IDs for the later authorized reconcile command. Keep Plan 1’s call order and never create runs, receipts, or CAS updates during standalone preflight.

Status/list/check JSON must include separate remote and local sections. In remote-required mode, a failed remote read is exit 3 even if the local board is readable. A local-mode client that sees a remote-required board raises exit 4 with an update-configuration message. Add tests for both mismatch directions.

- [ ] **Step 5: Update the canonical workflow document**

Insert a coordination section after live preflight explaining that local mode is the compatibility/rollback mode and remote-required makes the Git board authoritative. Document the exact env names, branch layout, orphan bootstrap, depth-one unique temporary refs, plain fast-forward push, no force/deletion, five retries, claim-id fencing, TTL/skew, remote-first/local-second compensation, remote-lagging/held-in-error, direct legacy sentinel, and separate board labels. Add the maintenance-window rollout in the exact eight-step order and rollback sequence from the spec. State that cross-machine resume trusts only remotely re-verifiable facts; Plan 2b will add the command details. Keep the existing bridge example and terminal-outcome/evidence wording intact.

- [ ] **Step 6: Run CLI/document tests and the full isolated script gate**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_run_cli.py tests/unit/scripts/test_nous_loop_contract.py tests/unit/scripts/test_loop_bridge.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
git diff --check
~~~

Expected: PASS for local/remote backend selection, no fallback, preflight no-run creation, sentinel behavior, canonical-document static contracts, and all legacy bridge tests; diff check is silent.

- [ ] **Step 7: Commit mode selection and docs**

~~~bash
git add scripts/nous/preflight.py scripts/nous_run.py scripts/loop_bridge.py docs/engineering/nous-loop.md tests/unit/scripts/test_nous_run_cli.py tests/unit/scripts/test_nous_loop_contract.py
git commit -m "feat(nous): wire remote-required mode and rollout contract"
~~~

### Task 5: Freeze workflow safety and retention/no-force contracts

**Files:**
- Create: tests/unit/scripts/test_nous_coordination_contract.py
- Modify: scripts/nous/gitio.py
- Modify: scripts/nous/backend_git.py

**Interfaces:**
- Consumes GitIO.validate_push_args and GitBackend.gc. Plan 2b will export publication trigger constants from publish.py; the scanner asserts that later set equals the current opencode trigger phrases.
- Produces scan_workflow_triggers(paths: Iterable[Path], *, coordination_branch: str) -> WorkflowScanResult and WorkflowScanError. The scanner is pure stdlib, conservative, fails closed when an on/push/pull_request block uses syntax it cannot classify, parses the repository YAML subset without PyYAML, detects branch/path filters, and proves no push or pull_request trigger can match nous-coordination.
- Produces AST-based source tests rejecting subprocess imports/calls outside gitio.py, plus runtime tests feeding every force/deletion refspec to validate_push_args. They also inspect the argparse command set/public APIs to assert no scripts/nous module implements compaction or remote deletion. Raw substring scans are not used because gitio.py must contain the deny-list literals and documentation may describe the threats.
- Contract tests read every .github/workflows/*.yml and freeze the current no-trigger result: test-pipeline.yml and secret-scan.yml branch-filter main/develop; workflow-lint.yml and helm-validate.yml branch/path-filter main/develop; trigger-deploy.yml main; all other workflows are non-push or workflow-dispatch/run/comment based. The scanner fails if a new workflow has an unclassified trigger.

- [ ] **Step 1: Write failing scanner/static tests**

~~~python
def test_no_workflow_trigger_matches_coordination_branch():
    result = scan_workflow_triggers(
        sorted(Path(".github/workflows").glob("*.yml")),
        coordination_branch="nous-coordination",
    )
    assert result.push_matches == ()
    assert result.pull_request_matches == ()


def test_unknown_trigger_syntax_fails_closed(tmp_path):
    workflow = tmp_path / "unknown.yml"
    workflow.write_text("on:\n  push:\n    branches: dynamic-branch-expression\n", encoding="utf-8")
    with pytest.raises(WorkflowScanError):
        scan_workflow_triggers([workflow], coordination_branch="nous-coordination")


def test_no_force_and_no_shell_outside_gitio():
    import ast
    for path in Path("scripts/nous").glob("*.py"):
        if path.name == "gitio.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            (isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names))
            or (isinstance(node, ast.ImportFrom) and node.module == "subprocess")
            for node in ast.walk(tree)
        )
~~~

- [ ] **Step 2: Run scanner tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_coordination_contract.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL because the scanner and static contract module are not present.

- [ ] **Step 3: Implement the conservative stdlib workflow scanner and static guards**

Parse only indentation-based keys, inline lists, and quoted scalar branch/path values needed by the repository. Treat a bare on scalar, expression, anchor, alias, unknown event shape, or dynamic branches/paths as WorkflowScanError rather than assuming it is safe. For push/pull_request, compute whether a literal coordination branch is allowed by branches/branches-ignore; a path filter cannot make a branch-filtered main/develop workflow match. Report filename/event/reason for any match. Use no YAML dependency.

Add AST tests for subprocess imports/calls outside gitio.py, runtime tests for force flags, plus push refspecs, and remote branch deletion, and parser/API inspection proving no compaction command exists. Keep the runtime guard in GitIO even though the structural tests exist; branch ruleset enforcement remains an operator prerequisite.

- [ ] **Step 4: Run workflow/no-force tests and all isolated tests**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_coordination_contract.py tests/unit/scripts/test_nous_gitio.py tests/unit/scripts/test_nous_git_backend.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for all workflow files, fail-closed unknown syntax, no force/deletion/runtime shell, and all previous Plan 0–1 tests.

- [ ] **Step 5: Commit contract guards**

~~~bash
git add tests/unit/scripts/test_nous_coordination_contract.py scripts/nous/gitio.py scripts/nous/backend_git.py
git commit -m "test(nous): freeze coordination branch safety contracts"
~~~

## Plan-level verification and rollout acceptance evidence

Run after all task commits:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
python3 -m compileall -q scripts/nous scripts/nous_run.py
python3 - <<'PY'
from pathlib import Path
assert Path("docs/engineering/nous-loop.md").read_text(encoding="utf-8").count("remote-required") >= 1
assert not any("+x:refs/heads/nous-coordination" in p.read_text(encoding="utf-8") for p in Path("scripts/nous").glob("*.py"))
print("Plan 2a static acceptance ok")
PY
git diff --check
~~~

Expected: all isolated tests PASS, compileall and diff check are silent, and Plan 2a static acceptance ok prints. A reviewer must retain evidence of a two-clone bare-repository bootstrap race with exactly one root, a full-snapshot CAS history, the 3-hour/45-minute renewal policy, claim-id loss fencing, compensation-pending retry, remote/local board labels, mode mismatch refusal, 30-day GC without history rewrite, and workflow/no-force guards. Before enabling production remote-required, an operator must stop both loops, reconcile/release local claims, update both clients, bootstrap the orphan branch in remote-required mode, configure both machines and sentinels, apply a GitHub ruleset blocking force-push/deletion while allowing ordinary fast-forward pushes, run the two-machine smoke test, then restart loops. Rollback evidence is both loops stopped, both clients set to local, remote claims released or allowed to expire, and the inert coordination branch retained.
