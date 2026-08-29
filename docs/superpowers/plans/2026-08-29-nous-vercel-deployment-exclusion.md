# NOUS Vercel Deployment Exclusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Git-backed NOUS coordination tree to a versioned schema that carries an immutable Vercel auto-deployment opt-out and migrate the live board without creating a claim or tick.

**Architecture:** Schema-1 snapshots remain read-compatible during a maintenance window. Schema-2 snapshots require exact repository-owned `vercel.json` bytes; bootstrap and every changed CAS snapshot write schema 2, while an explicit authorized migration performs the claim-free one-way upgrade. The live migration waits until Mac and Linux run the same merged client revision.

**Tech Stack:** Python 3.11+ standard library, pytest, local bare Git repositories, GitHub CLI for post-migration read-only evidence, and Vercel static Git configuration.

**Spec:** `docs/superpowers/specs/2026-08-29-nous-vercel-deployment-exclusion-design.md`

## Global Constraints

- Preserve `NOUS Coordination <nous-coordination@invalid>` exactly.
- Preserve orphan history, full-snapshot child commits, ordinary fast-forward pushes, the five-attempt CAS bound, and every force/deletion guard.
- Claims schema 1 is legacy read-only input; claims schema 2 is the only format new backend writes may produce. Run projection schema stays 1.
- Schema 1 allows only `claims.json` and `runs/<run-id>.json`; schema 2 additionally requires exact root `vercel.json` bytes.
- A missing, modified, or partial schema-2 guard fails closed before any mutation callback.
- Migration requires `coordinate`, `remote-required`, an empty stored claims array, and target schema 2.
- Do not add a Vercel collaborator, change deployment protection, write `.remote-required`, create a claim, or run a NOUS tick.
- Do not migrate the remote board until Mac and Linux pass focused tests at the same merged `develop` SHA.
- Run repository commands as `clawdbot`; never print credentials, secret files, credential-bearing URLs, or complete environments.

---

### Task 1: Version the snapshot codec and add the immutable guard

**Files:**
- Modify: `scripts/nous/backend_git.py:280-530`
- Modify: `tests/unit/scripts/test_nous_git_backend.py:1-140,438-486`

**Interfaces:**
- Produces `LEGACY_COORDINATION_SCHEMA = 1`, `CURRENT_COORDINATION_SCHEMA = 2`, and `VERCEL_DEPLOYMENT_GUARD: bytes`.
- Adds final field `schema: int = CURRENT_COORDINATION_SCHEMA` to `CoordinationSnapshot`, preserving existing four-positional-argument constructors.
- Changes `decode_claims_document(raw)` to return `(schema, mode, updated_at, claims)`.
- Keeps every public claim/run backend method unchanged.

- [ ] **Step 1: Write failing bootstrap and compatibility tests**

Add this import and test helper:

```python
from scripts.nous.backend_git import (
    CURRENT_COORDINATION_SCHEMA,
    LEGACY_COORDINATION_SCHEMA,
    VERCEL_DEPLOYMENT_GUARD,
    CoordinationSnapshot,
    GitBackend,
    GitBackendConfig,
    decode_claims_document,
)


def git_bytes(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, check=True
    ).stdout
```

Add behavior tests:

```python
def test_bootstrap_writes_schema2_and_exact_vercel_guard(two_backends):
    _, (left, _) = two_backends
    root = left.bootstrap()
    assert git(left.io.repo_root, "rev-list", "--max-parents=0", root) == root
    assert git(
        left.io.repo_root, "ls-tree", "-r", "--name-only", root
    ).splitlines() == ["claims.json", "vercel.json"]
    claims = json.loads(git(left.io.repo_root, "show", f"{root}:claims.json"))
    assert claims["schema"] == CURRENT_COORDINATION_SCHEMA
    assert git_bytes(left.io.repo_root, "show", f"{root}:vercel.json") == (
        VERCEL_DEPLOYMENT_GUARD
    )


def test_schema1_without_guard_remains_readable(two_backends):
    _, (left, _) = two_backends
    raw = (
        json.dumps(
            {
                "schema": LEGACY_COORDINATION_SCHEMA,
                "mode": "remote-required",
                "updated_at": "2026-08-27T04:00:00+00:00",
                "claims": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    root = left.io.commit_snapshot(
        {"claims.json": raw}, parent=None, message="legacy bootstrap"
    )
    left.io.push_fast_forward("origin", root, "nous-coordination")
    assert left.list() == []


@pytest.mark.parametrize("guard", (None, b"{}\n"))
def test_schema2_requires_exact_vercel_guard(two_backends, guard):
    _, (left, _) = two_backends
    claims = (
        json.dumps(
            {
                "schema": CURRENT_COORDINATION_SCHEMA,
                "mode": "remote-required",
                "updated_at": "2026-08-27T04:00:00+00:00",
                "claims": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    files = {"claims.json": claims}
    if guard is not None:
        files["vercel.json"] = guard
    root = left.io.commit_snapshot(files, parent=None, message="invalid schema2")
    left.io.push_fast_forward("origin", root, "nous-coordination")
    with pytest.raises(ValidationError):
        left.list()


def test_schema1_rejects_partial_guard_migration(two_backends):
    _, (left, _) = two_backends
    claims = (
        json.dumps(
            {
                "schema": LEGACY_COORDINATION_SCHEMA,
                "mode": "remote-required",
                "updated_at": "2026-08-27T04:00:00+00:00",
                "claims": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    root = left.io.commit_snapshot(
        {"claims.json": claims, "vercel.json": VERCEL_DEPLOYMENT_GUARD},
        parent=None,
        message="partial migration",
    )
    left.io.push_fast_forward("origin", root, "nous-coordination")
    with pytest.raises(ValidationError):
        left.list()
```

- [ ] **Step 2: Run the tests and verify the expected red result**

Run:

```bash
PYTHONPATH=. pytest \
  tests/unit/scripts/test_nous_git_backend.py::test_bootstrap_writes_schema2_and_exact_vercel_guard \
  tests/unit/scripts/test_nous_git_backend.py::test_schema1_without_guard_remains_readable \
  tests/unit/scripts/test_nous_git_backend.py::test_schema2_requires_exact_vercel_guard \
  tests/unit/scripts/test_nous_git_backend.py::test_schema1_rejects_partial_guard_migration \
  -q -p no:cacheprovider --no-cov
```

Expected: collection fails because the schema constants and guard do not exist. Correct any unrelated test error and rerun until missing protocol behavior is the cause.

- [ ] **Step 3: Implement the minimal versioned codec**

Add the exact constants:

```python
LEGACY_COORDINATION_SCHEMA = 1
CURRENT_COORDINATION_SCHEMA = 2
VERCEL_DEPLOYMENT_GUARD = (
    b'{\n'
    b'  "$schema": "https://openapi.vercel.sh/vercel.json",\n'
    b'  "git": {\n'
    b'    "deploymentEnabled": false\n'
    b'  }\n'
    b'}\n'
)
```

Change the claims decoder and snapshot model:

```python
def decode_claims_document(
    raw: bytes,
) -> tuple[int, str, str, tuple[Claim, ...]]:
    value = _load_json(raw, CLAIMS_MAX_BYTES, "claims.json")
    item = _object(value, {"schema", "mode", "updated_at", "claims"}, "claims.json")
    schema = item["schema"]
    if schema not in {LEGACY_COORDINATION_SCHEMA, CURRENT_COORDINATION_SCHEMA}:
        raise _validation("claims.json schema is incompatible")
    if item["mode"] not in {"local", "remote-required"}:
        raise _validation("claims.json mode is incompatible")
    updated_at = validate_timestamp(item["updated_at"])
    raw_claims = item["claims"]
    if not isinstance(raw_claims, list):
        raise _validation("claims must be a list")
    claims = tuple(_claim_from_json(value) for value in raw_claims)
    return schema, item["mode"], updated_at, claims


@dataclass(frozen=True)
class CoordinationSnapshot:
    mode: str
    updated_at: str
    claims: tuple[Claim, ...]
    runs: Mapping[str, RunProjection]
    schema: int = CURRENT_COORDINATION_SCHEMA
```

Make `serialize_claims()` emit `snapshot.schema`. Make `_files()` add exact `vercel.json` only for schema 2. In `_decode_snapshot()`, read `claims.json` first, then enforce:

```python
if schema == LEGACY_COORDINATION_SCHEMA:
    if "vercel.json" in paths:
        raise _validation("schema 1 snapshot contains a partial deployment guard")
else:
    if "vercel.json" not in paths:
        raise _validation("schema 2 snapshot is missing the deployment guard")
    if self.io.cat_file(commit, "vercel.json") != VERCEL_DEPLOYMENT_GUARD:
        raise _validation("schema 2 deployment guard is invalid")
```

Skip `vercel.json` in the run-file loop. Before `_cas()` compares snapshots, normalize legacy output:

```python
after, result = operation(before)
if after.schema != CURRENT_COORDINATION_SCHEMA:
    after = replace(after, schema=CURRENT_COORDINATION_SCHEMA)
if after == before:
    return result
```

This central normalization covers both positional constructors and `replace(snapshot, ...)` paths.

- [ ] **Step 4: Run the Git backend suite green**

Run:

```bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_git_backend.py \
  -q -p no:cacheprovider --no-cov
```

Expected: all tests pass. Update the pre-existing atomic-snapshot assertion to include `vercel.json` in sorted tree order.

- [ ] **Step 5: Commit the codec**

```bash
git add scripts/nous/backend_git.py tests/unit/scripts/test_nous_git_backend.py
git commit -m "fix(nous): embed Vercel deployment guard"
```

---

### Task 2: Add the explicit claim-free migration

**Files:**
- Modify: `scripts/nous/backend_git.py:418-580,956-985`
- Modify: `tests/unit/scripts/test_nous_git_backend.py`

**Interfaces:**
- Produces `SchemaMigration(previous_schema: int, current_schema: int, tip: str, changed: bool)`.
- Produces `GitBackend.migrate_schema(*, target: int) -> SchemaMigration`.
- Refuses any stored claim with `Conflict`, preserves run blobs, uses `_cas("bootstrap", ...)`, and creates no commit when already schema 2.

- [ ] **Step 1: Write failing migration tests**

Add a helper that converts a test-only schema-2 tip to a valid schema-1 child while preserving run blobs:

```python
def downgrade_tip_to_schema1(backend: GitBackend) -> str:
    repo = backend.io.repo_root
    git(repo, "fetch", "origin", "nous-coordination")
    tip = git(repo, "rev-parse", "FETCH_HEAD")
    paths = git(repo, "ls-tree", "-r", "--name-only", tip).splitlines()
    claims = json.loads(git(repo, "show", f"{tip}:claims.json"))
    claims["schema"] = LEGACY_COORDINATION_SCHEMA
    files = {
        "claims.json": (
            json.dumps(claims, indent=2, sort_keys=True) + "\n"
        ).encode()
    }
    for path in paths:
        if path.startswith("runs/"):
            files[path] = git_bytes(repo, "show", f"{tip}:{path}")
    legacy = backend.io.commit_snapshot(files, parent=tip, message="legacy fixture")
    backend.io.push_fast_forward("origin", legacy, "nous-coordination")
    return legacy
```

Add tests:

```python
def test_migration_preserves_runs_and_creates_one_fast_forward_child(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    claim = left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    left.release(run_id=RUN_A, claim_id=claim.claim_id, reason="fixture")
    legacy = downgrade_tip_to_schema1(left)
    before_run = git_bytes(left.io.repo_root, "show", f"{legacy}:runs/{RUN_A}.json")

    result = left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)

    assert (result.previous_schema, result.current_schema, result.changed) == (1, 2, True)
    assert git(left.io.repo_root, "rev-parse", f"{result.tip}^") == legacy
    assert git_bytes(left.io.repo_root, "show", f"{result.tip}:runs/{RUN_A}.json") == before_run
    repeated = left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)
    assert repeated.changed is False
    assert repeated.tip == result.tip


def test_migration_refuses_nonempty_claim_board_without_writing(two_backends):
    _, (left, _) = two_backends
    left.bootstrap()
    left.claim(**claim_kwargs(RUN_A, "mac", "fix/a", "streaming"))
    legacy = downgrade_tip_to_schema1(left)
    with pytest.raises(Conflict, match="empty claim board"):
        left.migrate_schema(target=CURRENT_COORDINATION_SCHEMA)
    git(left.io.repo_root, "fetch", "origin", "nous-coordination")
    assert git(left.io.repo_root, "rev-parse", "FETCH_HEAD") == legacy
```

- [ ] **Step 2: Run migration tests red**

```bash
PYTHONPATH=. pytest \
  tests/unit/scripts/test_nous_git_backend.py::test_migration_preserves_runs_and_creates_one_fast_forward_child \
  tests/unit/scripts/test_nous_git_backend.py::test_migration_refuses_nonempty_claim_board_without_writing \
  -q -p no:cacheprovider --no-cov
```

Expected: FAIL because `SchemaMigration` and `migrate_schema` do not exist.

- [ ] **Step 3: Implement the result and migration operation**

Add:

```python
@dataclass(frozen=True)
class SchemaMigration:
    previous_schema: int
    current_schema: int
    tip: str
    changed: bool
```

Refactor `_read()` through `_read_with_tip(*, allow_missing=False) -> tuple[str, CoordinationSnapshot] | None` while preserving unique temp-ref cleanup. Implement:

```python
@_schema_boundary
def migrate_schema(self, *, target: int) -> SchemaMigration:
    if target != CURRENT_COORDINATION_SCHEMA:
        raise _validation("only coordination schema 2 is supported")

    def apply(snapshot: CoordinationSnapshot):
        if snapshot.claims:
            raise Conflict("coordination schema migration requires an empty claim board")
        if snapshot.schema == target:
            return snapshot, (snapshot.schema, False)
        if snapshot.schema != LEGACY_COORDINATION_SCHEMA:
            raise _validation("coordination schema cannot be migrated")
        return replace(snapshot, schema=target, updated_at=_iso(self.clock())), (
            snapshot.schema,
            True,
        )

    previous_schema, changed = self._cas("bootstrap", apply)
    current = self._read_with_tip()
    assert current is not None
    tip, snapshot = current
    if snapshot.schema != target:
        raise TransportFailure("coordination schema migration was not observable")
    return SchemaMigration(previous_schema, snapshot.schema, tip, changed)
```

Export the constants and result. Add no downgrade, repair, deletion, or force path.

- [ ] **Step 4: Run migration and transport tests green**

```bash
PYTHONPATH=. pytest \
  tests/unit/scripts/test_nous_git_backend.py \
  tests/unit/scripts/test_nous_gitio.py \
  tests/unit/scripts/test_nous_coordination_contract.py \
  -q -p no:cacheprovider --no-cov
```

Expected: all tests pass, including identity and no-force contracts.

- [ ] **Step 5: Commit the migration API**

```bash
git add scripts/nous/backend_git.py tests/unit/scripts/test_nous_git_backend.py
git commit -m "feat(nous): add schema 2 migration"
```

---

### Task 3: Expose the authorized migration CLI

**Files:**
- Modify: `scripts/nous_run.py:15-260`
- Modify: `tests/unit/scripts/test_nous_run_cli.py:1-120`

**Interfaces:**
- Adds `nous_run.py migrate --to-schema 2 --authorize coordinate`.
- Success JSON contains only `branch`, `changed`, `from_schema`, `to_schema`, and `tip`.
- Missing authorization or local mode exits 4; live-claim conflict exits 2.

- [ ] **Step 1: Write failing parser, authorization, mode, and output tests**

Update the exact subcommand set to include `migrate`, import `SchemaMigration`, then add:

```python
def test_migrate_cli_requires_coordinate_and_remote_required(monkeypatch, tmp_path):
    config = SimpleNamespace(coord_mode="local")
    monkeypatch.setattr(nous_run, "_config", lambda _repo: config)
    missing_auth = build_parser().parse_args(["migrate", "--to-schema", "2"])
    with pytest.raises(ValidationError, match="authorization"):
        nous_run._dispatch(missing_auth, tmp_path)
    authorized = build_parser().parse_args(
        ["migrate", "--to-schema", "2", "--authorize", "coordinate"]
    )
    with pytest.raises(ValidationError, match="remote-required"):
        nous_run._dispatch(authorized, tmp_path)


def test_migrate_cli_reports_only_schema_and_tip(monkeypatch, tmp_path, capsys):
    tip = "23c3551a30ac5d230f68a01b76650c27144571f5"
    config = SimpleNamespace(
        coord_mode="remote-required", coordination_branch="nous-coordination"
    )

    class Remote:
        def migrate_schema(self, *, target):
            assert target == 2
            return SchemaMigration(1, 2, tip, True)

    monkeypatch.setattr(nous_run, "_config", lambda _repo: config)
    monkeypatch.setattr(nous_run, "_remote", lambda *_args: Remote())
    args = build_parser().parse_args(
        ["migrate", "--to-schema", "2", "--authorize", "coordinate"]
    )
    assert nous_run._dispatch(args, tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {
        "branch": "nous-coordination",
        "changed": True,
        "from_schema": 1,
        "tip": tip,
        "to_schema": 2,
    }
```

- [ ] **Step 2: Run the CLI tests red**

```bash
PYTHONPATH=. pytest \
  tests/unit/scripts/test_nous_run_cli.py::test_cli_exposes_only_coordination_milestone_commands \
  tests/unit/scripts/test_nous_run_cli.py::test_migrate_cli_requires_coordinate_and_remote_required \
  tests/unit/scripts/test_nous_run_cli.py::test_migrate_cli_reports_only_schema_and_tip \
  -q -p no:cacheprovider --no-cov
```

Expected: FAIL because `migrate` is absent.

- [ ] **Step 3: Implement parser and dispatch**

Add:

```python
migrate = commands.add_parser("migrate")
migrate.add_argument("--to-schema", type=int, choices=(2,), required=True)
migrate.add_argument("--authorize", action="append")
```

Handle it before `_combined()`:

```python
if args.command == "migrate":
    _require_coordinate(args)
    if config.coord_mode != "remote-required":
        raise ValidationError(
            SchemaError("migration requires remote-required mode"),
            message="set NOUS_COORD_MODE=remote-required before migration",
        )
    result = _remote(config, repo_root).migrate_schema(target=args.to_schema)
    print(json.dumps({
        "branch": config.coordination_branch,
        "changed": result.changed,
        "from_schema": result.previous_schema,
        "tip": result.tip,
        "to_schema": result.current_schema,
    }, sort_keys=True))
    return 0
```

This path creates no local mutex, receipt, claim, run, or sentinel.

- [ ] **Step 4: Run CLI tests and help output green**

```bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_run_cli.py \
  -q -p no:cacheprovider --no-cov
python3 scripts/nous_run.py --help
python3 scripts/nous_run.py migrate --help
```

Expected: tests pass; help exposes schema 2 and authorization without environment values.

- [ ] **Step 5: Commit the CLI**

```bash
git add scripts/nous_run.py tests/unit/scripts/test_nous_run_cli.py
git commit -m "feat(nous): expose guarded schema migration"
```

---

### Task 4: Update the canonical and historical protocol documents

**Files:**
- Modify: `docs/engineering/nous-loop.md:76-144`
- Modify: `docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md`
- Modify: `docs/superpowers/plans/2026-08-27-nous-plan-2a-git-coordination.md:1-35`

**Interfaces:**
- Produces one consistent operator contract for schema 1 compatibility, schema 2 guard enforcement, and two-machine migration order.
- Human prose receives no brittle source-text test; executable behavior is covered by Tasks 1-3.

- [ ] **Step 1: Update the canonical workflow**

Replace the claims/runs-only statement with:

```markdown
Claims schema 1 is the legacy, read-compatible tree and contains only
`claims.json` and `runs/<run-id>.json`. Claims schema 2 is the current write
format and additionally requires the repository-owned root `vercel.json`
whose exact `git.deploymentEnabled: false` value prevents the orphan data ref
from triggering Vercel. Unknown files, a schema-1 partial guard, or a missing
or modified schema-2 guard fail closed.
```

Document:

```bash
python3 scripts/nous_run.py migrate --to-schema 2 --authorize coordinate
```

State that both clients must pass focused tests at one merged SHA before migration, migration requires an empty stored claims array, and any Vercel deployment on the migration SHA stops rollout. Preserve the current no-tick and no-sentinel gates.

- [ ] **Step 2: Mark the original design and Plan 2a as superseded where needed**

Add this Plan 2a note:

```markdown
> **Protocol addendum (2026-08-29):** The schema-2 Vercel deployment guard in
> `docs/superpowers/specs/2026-08-29-nous-vercel-deployment-exclusion-design.md`
> supersedes this plan's claims/runs-only tree assertions. The original steps
> remain historical implementation evidence for schema 1.
```

Update the original design's source hierarchy, remote tree, Vercel threat row, rollout, acceptance criteria, and settled decisions so schema 2 is not described as foreign metadata.

- [ ] **Step 3: Review every conflicting phrase and whitespace**

```bash
rg -n "contains only|contains exactly|claims.json.*runs/|schema 2|deploymentEnabled|migrate --to-schema" \
  docs/engineering/nous-loop.md \
  docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md \
  docs/superpowers/specs/2026-08-29-nous-vercel-deployment-exclusion-design.md \
  docs/superpowers/plans/2026-08-27-nous-plan-2a-git-coordination.md
git diff --check
```

Expected: historical schema-1 wording is labeled legacy/superseded; current instructions consistently require schema 2 and the exact guard.

- [ ] **Step 4: Commit documentation**

```bash
git add docs/engineering/nous-loop.md \
  docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md \
  docs/superpowers/plans/2026-08-27-nous-plan-2a-git-coordination.md
git commit -m "docs(nous): document schema 2 deployment guard"
```

---

### Task 5: Verify, review, and publish the implementation

**Files:**
- Verify: every Task 1-4 file
- Verify: `scripts/nous/`, `scripts/nous_run.py`, `tests/unit/scripts/`

**Interfaces:**
- Produces a reviewed feature-branch head with exact local evidence.
- Does not mutate `nous-coordination` or Vercel.

- [ ] **Step 1: Run complete NOUS and static gates**

```bash
PYTHONPATH=. pytest tests/unit/scripts/ \
  --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
python3 -m compileall -q scripts/nous scripts/nous_run.py
python3 scripts/nous_run.py --help
git diff --check
```

Record the exact pass count and all warnings.

- [ ] **Step 2: Run repository local CI from a fresh base**

As `clawdbot`:

```bash
git fetch --no-tags origin develop
scripts/ci/run_local_ci.sh --base origin/develop
```

Record passed, failed, and skipped gates exactly. Missing dependencies/services are skips or blockers, never passes.

- [ ] **Step 3: Review the final diff against the approved spec**

```bash
git diff --stat origin/develop...HEAD
git diff --check origin/develop...HEAD
git diff origin/develop...HEAD -- scripts/nous/backend_git.py scripts/nous_run.py \
  tests/unit/scripts/test_nous_git_backend.py tests/unit/scripts/test_nous_run_cli.py \
  docs/engineering/nous-loop.md \
  docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md \
  docs/superpowers/plans/2026-08-27-nous-plan-2a-git-coordination.md
```

Check exact guard bytes, schema file sets, central write normalization, live-claim refusal, idempotence, and absence of identity/force/deletion/sentinel/claim/tick changes.

- [ ] **Step 4: Obtain code review and rerun after changes**

Use `superpowers:requesting-code-review`. Any code change invalidates review evidence and requires rerunning focused causal tests plus the full isolated suite.

- [ ] **Step 5: Publish only with current authorization**

If branch push and PR creation are authorized, push `codex/fix-nous-vercel-deployments` and open a PR to `develop` containing the observed failure, root cause, red/green evidence, exact gate output, warnings/skips, and review findings. Otherwise stop at the local SHA.

Do not merge without current merge authorization and green required hosted checks. A merge does not authorize Task 6 until its preconditions pass.

---

### Task 6: Perform the coordinated remote migration and Vercel acceptance check

**Files:**
- Remote append-only branch: `refs/heads/nous-coordination`
- Read-only evidence: GitHub deployments, statuses, rulesets, and branch tree

**Interfaces:**
- Produces one schema-2 fast-forward commit with an empty claims array and exact guard bytes.
- Produces evidence that Vercel created no deployment/status for that SHA.
- Does not create a claim, sentinel, receipt, or tick.

- [ ] **Step 1: Verify maintenance-window preconditions on both machines**

On Mac and Linux: loops stopped; same exact merged `develop` SHA; focused backend/CLI tests pass; UTC/NTP synchronized; exact active branch ruleset still blocks deletion and non-fast-forward only; the remote stored claims array and both local live-claim views are empty; `.remote-required` is absent.

Any failed or unverifiable item stops before mutation.

- [ ] **Step 2: Configure only the migration shell**

On Linux, use the already approved paths and identity:

```bash
export NOUS_COORD_MODE=remote-required
export NOUS_COORD_GIT_REMOTE=origin
export NOUS_GITHUB_REPOSITORY=Goodwiinz/rag
export NOUS_COORD_BRANCH=nous-coordination
export NOUS_MACHINE_ID=linux-onubuntu
export LOOP_BRIDGE_DIR=/home/clawdbot/.loop-bridge
export NOUS_RECEIPT_DIR=/home/clawdbot/.nous-runs/rag
```

On the Mac, reuse its pre-existing verified machine ID, mutex directory, and
receipt directory from the current NOUS configuration. If any value is absent
or ambiguous, stop before migration. Do not persist or print either host's
shell values.

- [ ] **Step 3: Record the legacy tip and migrate once**

From one machine:

```bash
python3 scripts/nous_run.py migrate --to-schema 2 --authorize coordinate
```

Expected JSON: `from_schema=1`, `to_schema=2`, `changed=true`, and a validated 40-hex tip.

- [ ] **Step 4: Verify the new remote commit**

Freshly verify current tip, single-parent ancestry from the legacy tip, exact schema-2 tree, exact guard bytes, mode `remote-required`, an empty claims array, byte-identical pre-existing runs, dedicated committer identity, unchanged ruleset, and absence of sentinel/receipt files.

- [ ] **Step 5: Poll the real Vercel side effect**

For at least 120 seconds, at intervals no longer than 30 seconds, query structured fields from:

After validating the migration command's returned SHA into the shell variable
`coord_schema2_sha`, run:

```bash
gh api "repos/Goodwiinz/rag/deployments?sha=$coord_schema2_sha&per_page=100"
gh api "repos/Goodwiinz/rag/commits/$coord_schema2_sha/status"
gh api "repos/Goodwiinz/rag/commits/$coord_schema2_sha/check-suites"
```

Acceptance requires no deployment by `vercel[bot]` and no `Vercel` status for the schema-2 SHA. Other queued App suites are observations, not proof of Vercel success.

If Vercel creates any deployment, stop. Do not change identity, invite a collaborator, remove the guard, or write again. Preserve schema 2 and start the dedicated-repository fallback design.

- [ ] **Step 6: Stop claim-free and report**

Report both machine SHAs/tests, legacy/schema-2 SHAs, parentage, exact tree, schema/mode/claims, identity, ruleset, Vercel evidence, warnings/skips, and confirmation of no secret output, force push, sentinel, receipt, claim, or real tick.

Do not start the later two-machine claim smoke test in this plan.
