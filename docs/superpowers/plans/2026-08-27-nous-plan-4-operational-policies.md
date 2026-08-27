# NOUS operational policies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound review rounds, surface non-blocking pull-request size policy, automate 30-day retention, and render complete evidence-only operational summaries after GitHub reconciliation.

**Architecture:** receipt.py records review rounds as typed events and refuses a fourth round without mutating the run. preflight.py evaluates a soft size policy alongside existing freshness and authorization probes. summary.py and nous_run.py expose policy warnings, retention defaults, and reconcile-triggered garbage collection while consuming Plan 2b’s reconciliation and publication facts.

**Tech Stack:** Python 3.11+ standard library (dataclasses, datetime, json, pathlib, argparse, typing) and pytest only in tests/unit/scripts/; no new subprocess sites, YAML libraries, services, or network calls.

**Spec:** docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md

## Global Constraints

- Depends on Plan 2b and consumes its exact Reconciler, ReconciliationAction, PublicationResult, ResumeResult, ReceiptStore, and CLI interfaces; Plan 4 does not alter Git CAS, merge verification, marker ownership, or resume trust rules.
- Review rounds are bounded at MAX_REVIEW_ROUNDS = 3. The fourth attempted round is a typed policy rejection, leaves the receipt and remote projection unchanged, and reports ready-for-human with the claim retained when invoked from a live run.
- PR-size policy is soft: PR_SIZE_SOFT_LIMIT_LINES = 800 and PR_SIZE_SOFT_LIMIT_FILES = 50 produce warnings only; they never imply a passing gate, permit a merge, or replace the required permissions/checks.
- Retention is 30 days for ordinary terminal run projections. GC removes only terminal runs (including ready-for-human after its claim has aged out) through Plan 2a’s ordinary full-snapshot CAS; it never rewrites history, compacts, force-pushes, or deletes active runs.
- Generated summaries contain only receipt events, exact SHAs, gate names/results/skip lists, review-round records, policy warnings, publication facts, and reconciliation actions. Free-form GitHub text, credentials, prompts, and local paths stay out of remote bodies.
- The existing exit contract remains 0 success, 1 usage/internal, 2 conflict/claim refusal, 3 backend unavailable, and 4 validation/policy rejection. Legacy loop_bridge.py and its 45-minute TTL are not changed.
- Every task uses a red/green cycle and one scoped commit. Commands below are verification instructions; this plan does not claim that they have been run.

## File map and dependency boundary

| Path | Ownership in this plan |
| --- | --- |
| scripts/nous/receipt.py | Add bounded review-round event recording and policy rejection while preserving Plan 1 durability, state transitions, invalidation, and resume demotion. |
| scripts/nous/preflight.py | Add the soft PR-size policy result consumed by the operational CLI. |
| scripts/nous/summary.py | Render the complete event-only operational summary sections and policy warnings. |
| scripts/nous_run.py | Wire review, preflight size warnings, reconcile-time GC, status/terminal output, and the gc command without duplicating Plan 2b mutations. |
| tests/unit/scripts/test_nous_policies.py | Review-round, size-policy, retention-config, and reconcile/GC policy tests. |
| tests/unit/scripts/test_nous_summary.py | Extend Plan 1 summary tests for the complete section order and untrusted-data filtering. |
| tests/unit/scripts/test_nous_run_cli.py | Extend Plan 1/2b dispatch tests for policy warnings, gc, and stable policy exit codes. |
| tests/unit/scripts/test_nous_operational_contract.py | Read-only rollout/rollback, no-compaction, and retention contract tests. |

Plan 2b’s Reconciler.reconcile(*, authorization: Authorization) -> tuple[ReconciliationAction, ...], Reconciler.verify_merge(*, run_id: str, pr: int, reviewed_head_sha: str | None = None) -> MergeVerification, PublicationResult, and ResumeResult are consumed as already defined; this plan does not introduce alternate reconciliation or publication interfaces. Plan 1’s ReceiptStore.append(), current_projection(), load_events(), advance(), close(), PreflightResult, render_terminal_report(), render_status_json(), render_pr_body(), and map_error() remain source-compatible.

### Task 1: Record and enforce bounded review rounds

**Files:**
- Modify: scripts/nous/receipt.py (review-round policy beside ReceiptStore.advance)
- Modify: scripts/nous_run.py (review command dispatch and policy exit)
- Create: tests/unit/scripts/test_nous_policies.py
- Modify: tests/unit/scripts/test_nous_run_cli.py

**Interfaces:**
- Produces MAX_REVIEW_ROUNDS: int = 3, ReviewRound(round_number: int, head_sha: str, reviewer: str, outcome: str, detail: str | None), and ReviewLimitReached(ValidationError) with a stable message containing the limit value but no free-form detail.
- Produces ReceiptStore.record_review_round(*, head_sha: str, reviewer: str, outcome: str, detail: str | None = None) -> LocalProjection. It validates the exact lowercase 40-hex head, requires current state fixed or reviewed, accepts outcomes approved, changes-requested, and blocked, and increments review_rounds only after one durable review_round event append. That single event has state reviewed for approved and keeps/regresses state fixed for changes-requested or blocked; it reuses the internal transition validator without recursively calling the public lock-taking advance method.
- A fourth call raises ReviewLimitReached before append or projection replacement. It does not release a claim itself; the CLI maps this policy result to exit 4, and a caller that needs human handoff uses Plan 1 close(outcome="ready-for-human", blocker=Blocker(kind="review-unavailable", detail="review round limit reached")).
- Extends the CLI with review --run-id R --head-sha SHA --reviewer NAME --outcome approved|changes-requested|blocked. It loads the existing authorization/receipt/backend context, calls require_action(authorization, "coordinate") before remote metadata mutation, renews before the long review gate when required, records exactly one round, and synchronizes the projection through the ordinary fenced path. On a third non-approved result it prints a typed handoff recommendation; it does not silently perform a fourth round or infer permission for a different action.
- Consumes Plan 1 Event/LocalProjection/ReceiptStore locking and Plan 0 validate_sha, validate_agent, and Blocker; no new persistent schema field is required because review_round detail is already part of the event and review_rounds already exists in LocalProjection.

- [ ] **Step 1: Write failing review-round tests**

Create a store fixture that calls create_started, records reproduction and fixed events at HEAD, then exercises the limit:

~~~python
def test_three_review_rounds_are_recorded_and_fourth_is_atomic(store, HEAD):
    store.advance(to_state="claimed", evidence_head_sha=HEAD, tier="local",
                  detail={"claim_id": "c-a1b2c3d4e5f6"})
    store.advance(to_state="reproduced", evidence_head_sha=HEAD, tier="local",
                  detail={"reproduction": "reproduced at pinned head"})
    store.advance(to_state="fixed", evidence_head_sha=HEAD, tier="local",
                  detail={"causal_red": "failed", "causal_green": "passed"})
    for number in (1, 2, 3):
        store.record_review_round(head_sha=HEAD, reviewer="reviewer",
                                  outcome="changes-requested")
    before = (store.directory / "events.jsonl").read_bytes()
    before_projection = store.current_projection()
    with pytest.raises(ReviewLimitReached):
        store.record_review_round(head_sha=HEAD, reviewer="reviewer",
                                  outcome="approved")
    assert (store.directory / "events.jsonl").read_bytes() == before
    assert store.current_projection() == before_projection
    assert store.current_projection().review_rounds == 3
~~~

Also assert malformed SHA, unknown outcome, a fourth call after a reload, and a reviewer value containing a control byte are rejected before any event is written. Use a separate approved-round test to assert state reviewed and the event detail has round_number 1.

- [ ] **Step 2: Run the focused tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_policies.py -q -k 'review_round' -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because ReviewRound, MAX_REVIEW_ROUNDS, ReviewLimitReached, and ReceiptStore.record_review_round are not defined.

- [ ] **Step 3: Implement the minimal bounded policy**

Under the existing per-run lock, read the current projection, count durable review_round events (not an in-memory counter), compare with MAX_REVIEW_ROUNDS, validate reviewer through validate_agent and detail through the existing sanitize_detail path, then use a private lock-held append/projection helper to write exactly one review_round event. Rebuild current.json with the same fsync ordering already used by append. For approved, validate the fixed -> reviewed edge and set reviewed in that event; for changes-requested or blocked keep/regress fixed and retain the event. Never call public advance while holding the lock. Do not catch ReviewLimitReached in ReceiptStore, do not mutate remote state here, and do not include reviewer/detail in a remote projection except through the existing allowlisted event fields.

- [ ] **Step 4: Run the focused tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_policies.py -q -k 'review_round' -p no:cacheprovider --no-cov
~~~

Expected: PASS for three durable rounds, approved transition, exact event detail, validation-before-write, fourth-call no-op, and reload persistence.

- [ ] **Step 5: Commit the bounded policy**

~~~bash
git add scripts/nous/receipt.py scripts/nous_run.py tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_run_cli.py
git commit -m "feat: bound NOUS review rounds"
~~~

### Task 2: Surface the soft pull-request size policy in preflight

**Files:**
- Modify: scripts/nous/preflight.py (policy constants, result dataclasses, and run_preflight integration)
- Modify: tests/unit/scripts/test_nous_policies.py
- Modify: tests/unit/scripts/test_nous_run_cli.py

**Interfaces:**
- Produces PR_SIZE_SOFT_LIMIT_LINES: int = 800 and PR_SIZE_SOFT_LIMIT_FILES: int = 50.
- Produces frozen DiffStat(insertions: int, deletions: int, files: int), frozen SizePolicyResult(checked: bool, warning: str | None, diff: DiffStat | None), and evaluate_pr_size(diff: DiffStat | None) -> SizePolicyResult. Negative counts raise ValidationError; None means the size probe was unavailable and returns checked=False, warning=None.
- Consumes an optional diff_stat() -> DiffStat | None capability on PreflightProbes. Existing fake probes that do not provide this method remain valid because run_preflight uses a None result; no size warning is generated for a missing probe, and Plan 2a’s GitIOBackedPreflight may provide the method.
- Extends PreflightResult with size_policy: SizePolicyResult = field(default_factory=lambda: SizePolicyResult(checked=False, warning=None, diff=None)) and policy_warnings: tuple[str, ...] = (). Existing base/workspace/gates/authorization/mode/reconciled_runs/remote_run_created/ready_for_human fields and run_preflight keyword signature remain unchanged; adding these trailing defaults does not break Plan 1/2a callers.
- Consumes Plan 1 ALLOWED_ACTIONS, Authorization, WorkspaceFacts, GateInventory, PreflightResult, require_action, and Plan 2a GitIOBackedPreflight. The warning is informational and never satisfies a gate or authorization action.

- [ ] **Step 1: Write failing size-policy tests**

Add exact boundary tests:

~~~python
def test_size_policy_is_soft_and_reports_both_limits():
    result = evaluate_pr_size(DiffStat(insertions=600, deletions=300, files=51))
    assert result.checked is True
    assert result.warning == "PR size soft limit exceeded: 900 changed lines, 51 files"
    assert result.diff == DiffStat(600, 300, 51)

def test_size_at_limits_has_no_warning():
    assert evaluate_pr_size(DiffStat(500, 300, 50)).warning is None

def test_preflight_size_warning_does_not_authorize_merge(fake_probe, fake_backend, tmp_path):
    fake_probe.diff_stat = lambda: DiffStat(801, 0, 1)
    result = run_preflight(
        agent="agent", backend=fake_backend, probes=fake_probe,
        authorization=Authorization.from_names(("coordinate",)),
        mode="local",
    )
    assert result.policy_warnings == (
        "PR size soft limit exceeded: 801 changed lines, 1 files",
    )
    with pytest.raises(AuthorizationRequired):
        require_action(result, "merge")
~~~

Include negative-count rejection and a None probe test. The CLI test passes --json and asserts the warning is data under size_policy/policy_warnings, not a success or merge event.

- [ ] **Step 2: Run the focused tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_run_cli.py -q -k 'size_policy or preflight_size' -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because DiffStat, SizePolicyResult, evaluate_pr_size, and PreflightResult.size_policy are not defined.

- [ ] **Step 3: Implement the non-blocking size result**

Call diff_stat after the existing fetch/workspace/gate probes. Convert the counts to integers, reject negative values, use changed lines = insertions + deletions, and emit exactly one deterministic warning when either limit is strictly exceeded. Standalone preflight remains receipt-free; when claim consumes this result, it records the warning in that run's single local receipt. Never put the warning in claims.json or a remote run as a blocker. Preserve the existing no-remote-run-on-preflight rule and require_action behavior.

- [ ] **Step 4: Run the focused tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_run_cli.py -q -k 'size_policy or preflight_size' -p no:cacheprovider --no-cov
~~~

Expected: PASS at both boundaries, on missing probes, on negative validation, and on merge authorization remaining independent.

- [ ] **Step 5: Commit the size policy**

~~~bash
git add scripts/nous/preflight.py tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_run_cli.py
git commit -m "feat: report NOUS pull request size warnings"
~~~

### Task 3: Add retention defaults and complete event-only summaries

**Files:**
- Modify: scripts/nous/receipt.py (retention eligibility helper only; preserve GC implementation in Plan 2a)
- Modify: scripts/nous/summary.py
- Modify: scripts/nous_run.py
- Modify: tests/unit/scripts/test_nous_policies.py
- Modify: tests/unit/scripts/test_nous_summary.py
- Modify: tests/unit/scripts/test_nous_run_cli.py

**Interfaces:**
- Produces RETENTION_DAYS: int = 30, terminal_age(projection: Mapping[str, object], *, now: datetime) -> timedelta | None, and retention_eligible(projection: Mapping[str, object], *, now: datetime) -> bool. These functions read the newest milestone whose state is a terminal outcome and its at timestamp; they do not invent a terminal_at field. Only terminal outcomes merged, ready-for-human, dry, or cancelled strictly older than 30 days are eligible; active, malformed, and missing-timestamp projections return False. A ready-for-human projection is eligible only when claim_active is false, matching Plan 2a’s GC guard.
- Extends summary.render_terminal_report(events, projection) -> str with exact sections in this order: Current state, Evidence, Milestones, Gates, Review rounds, Policy warnings, Publication, Reconciliation, Blocker, and Outcome. Existing render_status_json and render_pr_body remain callable with their Plan 1/2b signatures and include the same allowlisted sections/data.
- Produces run_reconcile(*, reconciler: Reconciler, authorization: Authorization) -> tuple[ReconciliationAction, ...]. It calls the Plan 2b reconciler once with the current-request authorization; that reconciler requires coordinate and invokes Plan 2a GitBackend.gc() opportunistically at the end, so this wrapper never performs a second GC. The CLI gc command separately requires coordinate, calls backend.gc(*, now: datetime | None = None), and prints only returned run IDs/actions.
- Consumes RETENTION_DAYS and retention_eligible from this task, Plan 2a GitBackend.gc(*, now: datetime | None = None) -> tuple[str, ...], Plan 2b ReconciliationAction/Reconciler, Plan 1 event allowlist, and Plan 2b publication/reconciliation facts. It does not implement a second GC or inspect raw GitHub prose.

- [ ] **Step 1: Write failing retention and summary tests**

Use fixed UTC timestamps and event fixtures:

~~~python
def test_retention_keeps_ready_for_human_and_removes_old_cancelled():
    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    old = {"outcome": "cancelled", "claim_active": False,
           "milestones": ({"state": "cancelled", "at": "2026-08-30T00:00:00+00:00"},)}
    human = {"outcome": "ready-for-human", "claim_active": False,
             "milestones": ({"state": "ready-for-human", "at": "2026-08-01T00:00:00+00:00"},)}
    assert retention_eligible(old, now=now) is True
    assert retention_eligible(human, now=now) is True

def test_retention_is_strictly_older_than_thirty_days():
    now = datetime(2026, 9, 30, tzinfo=timezone.utc)
    at_limit = {"outcome": "dry", "claim_active": False,
                "milestones": ({"state": "dry", "at": "2026-08-31T00:00:00+00:00"},)}
    assert retention_eligible(at_limit, now=now) is False

def test_summary_has_fixed_operational_sections(events):
    report = render_terminal_report(
        events,
        {"state": "reviewed", "evidence_head_sha": HEAD, "review_rounds": 2,
         "policy_warnings": (
             "PR size soft limit exceeded: 801 changed lines, 1 files",
         )},
    )
    sections = [
        line.removeprefix("## ")
        for line in report.splitlines()
        if line.startswith("## ")
    ]
    assert sections == [
        "Current state", "Evidence", "Milestones", "Gates", "Review rounds",
        "Policy warnings", "Publication", "Reconciliation", "Blocker", "Outcome",
    ]
    assert "801 changed lines" in report
~~~

Also test the RETENTION_DAYS constant, ordinary terminal exactly at 30 days, active-claim and malformed/missing timestamp exclusions, summary exclusion of a fake GitHub instruction, and run_reconcile calling the reconciler exactly once (whose recorded actions include its single opportunistic GC call).

- [ ] **Step 2: Run the focused tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py -q -k 'retention or summary_sections or reconcile_gc' -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection or assertions because retention eligibility, complete section rendering, and run_reconcile are not defined.

- [ ] **Step 3: Implement retention wiring and allowlisted rendering**

Use the fixed RETENTION_DAYS = 30 policy and UTC-aware timestamps. Keep backend.gc responsible for CAS pruning and its 120-second skew rule; receipt.retention_eligible only determines the policy input/contract and must not delete files. Wire reconcile dispatch to the existing Reconciler.reconcile(authorization=current_authorization) so its one end-of-reconcile GC remains the only automatic deletion. Build every summary section from event fields and typed Plan 2b results. Emit empty sections with an explicit "none recorded" value instead of inventing success. Escape line breaks/control characters in display values through the existing summary sanitizer, retain exact SHA strings, and omit local paths, command output, comments, review text, and credentials.

- [ ] **Step 4: Run the focused tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py -q -k 'retention or summary_sections or reconcile_gc' -p no:cacheprovider --no-cov
~~~

Expected: PASS for the fixed 30-day boundary, active-claim/ready-for-human retention rules, one reconciler/GC call, exact section order, and event-only output.

- [ ] **Step 5: Commit retention and summaries**

~~~bash
git add scripts/nous/receipt.py scripts/nous/summary.py scripts/nous_run.py tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py
git commit -m "feat: add NOUS retention and operational summaries"
~~~

### Task 4: Freeze operational rollout, rollback, and maintenance contracts

**Files:**
- Create: tests/unit/scripts/test_nous_operational_contract.py

**Interfaces:**
- Produces test_rollout_order_and_rollback_are_documented(repo_root: Path) and test_scripts_do_not_offer_compaction_or_force_mutation(repo_root: Path), plus a pure-stdlib contract suite that reads the canonical spec and docs/engineering/nous-loop.md without executing commands or mutating GitHub.
- Consumes Plan 2a legacy_mutations_allowed(), has_remote_required_sentinel(), scan_workflow_triggers(), validate_push_args(), Plan 2b Reconciler/marker contracts, and Task 3 RETENTION_DAYS/retention_eligible()/run_reconcile(). It verifies ownership only; it does not reimplement those functions.
- The contract suite proves the eight operational rollout order constraints, rollback leaves the coordination branch inert while both clients return to local mode, retention is 30 days, ready-for-human claims are retained, compaction is not implemented by scripts/nous/, and all force/deletion paths are rejected by the existing runtime/static guards.

- [ ] **Step 1: Write failing operational contract tests**

Read the exact rollout section and assert ordered phrases, then check source constraints:

~~~python
def test_rollout_order_and_rollback_are_documented(repo_root):
    spec = (repo_root / "docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md").read_text()
    positions = [
        spec.index(phrase)
        for phrase in (
            "Stop the loop on both machines",
            "Reconcile and release all local claims",
            "Update both clients",
            "Bootstrap `nous-coordination`",
            "Configure the Git backend",
            "Apply the branch ruleset",
            "Two-machine smoke test",
            "Enable remote-required mode",
        )
    ]
    assert positions == sorted(positions)
    assert "set `NOUS_COORD_MODE=local` on both" in spec
    assert "30 days" in spec

def test_cli_has_no_compaction_command(parser):
    subcommands = parser_subcommand_names(parser)
    assert "gc" in subcommands
    assert "compact" not in subcommands


def test_force_and_delete_forms_are_rejected_by_runtime_guard():
    for args in (("push", "origin", "--force", "x:y"),
                 ("push", "origin", "--force-with-lease", "x:y"),
                 ("push", "origin", "--delete", "y"),
                 ("push", "origin", "+x:y")):
        with pytest.raises(ValidationError):
            validate_push_args(args)


def test_rollback_contract_returns_both_clients_to_local_without_deleting_branch(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    config = load_runtime_config({"NOUS_COORD_MODE": "local"}, repo_root=repo_root)
    assert config.coord_mode == "local"
    assert not has_remote_required_sentinel(tmp_path / "bridge")
    assert repo_root.name == "repo"
~~~

Add tests that scan every workflow through Plan 2a’s scanner, invoke validate_push_args with each force/deletion form, assert RETENTION_DAYS == 30 and retention_eligible rejects an active claim, and inspect argparse subparser choices to prove the CLI lists gc and never a compaction command. Do not grep for forbidden words: gitio.py necessarily contains its literal deny-list and documentation may discuss out-of-scope compaction.

- [ ] **Step 2: Run the focused contract tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_operational_contract.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL because the contract test module and its source assertions are absent before they are wired to the Plan 2a/2b interfaces.

- [ ] **Step 3: Implement the read-only contract helpers**

Keep the rollout text authoritative in the spec and make the test helpers call the real guards. Add no production mutation path and no new CLI command: gc/help and policy_warnings must already be supplied by Tasks 2–3. Ensure rollback tests inspect configuration/sentinel state rather than attempting a real remote reset. The workflow scanner remains fail-closed and PyYAML-free.

- [ ] **Step 4: Run the full isolated script gate and contract tests**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_operational_contract.py tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py tests/unit/scripts/test_loop_bridge.py tests/unit/scripts/test_nous_loop_contract.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS with no application/backend dependencies; the existing loop_bridge compatibility suite remains unchanged and the contract suite proves no compaction, force mutation, workflow trigger, retention, or rollback regression.

- [ ] **Step 5: Commit the operational contracts**

~~~bash
git add tests/unit/scripts/test_nous_operational_contract.py
git commit -m "test: freeze NOUS operational policies"
~~~

## Phase-level verification and acceptance evidence

Run the Plan 4 focused suite:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_policies.py tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py tests/unit/scripts/test_nous_operational_contract.py -q -p no:cacheprovider --no-cov
~~~

Expected evidence: three review rounds are durable and the fourth is an atomic rejection; size limits emit warnings without authorizing merge; retention is 30 days and reconcile performs one opportunistic GC; summaries have the ten required sections and contain only event-derived evidence; rollout/rollback/no-compaction/force/workflow contracts pass.

Then run the full isolated script gate without claiming a result until it completes:

~~~bash
scripts/ci/run_local_ci.sh
~~~

Expected evidence: the repository’s configured unit/contract checks pass, including tests/unit/scripts/, while no network or real GitHub mutation occurs. Finally inspect git diff --check and confirm only the Plan 4 paths listed above changed; do not commit generated artifacts or claim acceptance before the commands provide output.
