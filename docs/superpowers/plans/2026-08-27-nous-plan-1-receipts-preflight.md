# NOUS receipts and preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add crash-safe local receipts, the exact NOUS run state machine, freshness/authorization preflight, evidence-only summaries, and a local-mode CLI that consumes Plan 0’s coordination boundary.

**Architecture:** ReceiptStore is a per-run write-ahead log: it appends and fsyncs an event under a per-run lock, then atomically replaces current.json. State transitions and SHA-bound invalidation are centralized there. Preflight receives injectable repository probes so this phase has no subprocess site; the CLI maps typed errors to the stable exit contract, and Plan 2a supplies the guarded Git probe/backend.

**Tech Stack:** Python 3.11+ standard library (dataclasses, fcntl, json, os, pathlib, tempfile, typing, datetime, argparse) and pytest only in tests/unit/scripts/. Plan 0’s scripts.nous.coordination and backend_local are the only coordination dependencies.

**Spec:** docs/superpowers/specs/2026-08-27-nous-cross-machine-coordination-design.md

## Global Constraints

- Depends on Plan 0 and must consume its exact Claim, RunProjection, Candidate, CoordinationBackend, LocalMutex, Conflict, ClaimLost, BackendUnavailable, and ValidationError interfaces.
- New code remains pure standard library; no git or gh process is spawned in Plan 1 and no third-party import is permitted under scripts/nous/.
- events.jsonl is append-only; every event is flushed and fsync’d before current.json is replaced and the receipt directory is fsync’d.
- A malformed non-final event fails closed. A torn final line is preserved, reported, excluded from projection rebuild, and never silently rewritten.
- Every state milestone carries an exact lowercase 40-hex evidence_head_sha; local-only evidence is never represented as remote authority.
- A remote projection is not created speculatively during preflight. Plan 1’s local mode has no remote run projection.
- run_preflight is read-only: it calls only probe observations, creates no receipt, claim, lock, or remote projection, and returns facts for the caller to consume.
- The injected Authorization and returned preflight facts carry only action names from coordinate, push, create-pr, comment, merge, and change-ruleset; preflight never records credentials or infers authorization from an earlier request or receipt.
- New nous_run.py claim operations use a three-hour TTL (10,800 seconds); loop_bridge.py remains at 45 minutes.
- Exit codes are stable: 0 success, 1 usage/internal, 2 conflict/claim refused, 3 backend unavailable, 4 validation rejection.
- Every task has an explicit red/green cycle and one scoped commit. Do not implement Plan 2a/2b Git/GitHub behavior here.

## File map and cross-plan interfaces

| Path | Ownership in this plan |
| --- | --- |
| scripts/nous/receipt.py | Event schema, crash recovery, atomic current projection, state machine, head invalidation, resume demotion helper. |
| scripts/nous/preflight.py | Read-only probe protocols, workspace/base/gate checks, explicit authorization allowlist, and preflight result. |
| scripts/nous/summary.py | Event-derived terminal and status reports; rendering has no free-composed success assertions. |
| scripts/nous_run.py | Thin parser/dispatcher, local-mode backend selection, JSON output, exit-code mapping. |
| tests/unit/scripts/test_nous_receipt.py | Receipt durability, torn lines, transitions, invalidation, resume demotion. |
| tests/unit/scripts/test_nous_preflight.py | Probe/authorization/freshness contracts. |
| tests/unit/scripts/test_nous_summary.py | Event-only rendering and missing-evidence behavior. |
| tests/unit/scripts/test_nous_run_cli.py | Parser, local mode, output, and stable exit code contracts. |

Plan 2a consumes ReceiptStore.current_projection(), ReceiptStore.mark_remote_lagging(), and PreflightResult. Plan 2b consumes receipt events through load_events() and summary.render_pr_body(). Plan 3 consumes PreflightResult.candidates only after ledger normalization. No later plan may make run_preflight create a receipt.

### Task 1: Implement the crash-safe append-only receipt

**Files:**
- Create: scripts/nous/receipt.py
- Create: tests/unit/scripts/test_nous_receipt.py

**Interfaces:**
- Consumes Claim, Candidate, Milestone, Blocker, RunProjection, ValidationError, ClaimLost, and state constants from scripts.nous.coordination.
- Produces Event(seq: int, ts: str, event: str, state: str | None, evidence_head_sha: str | None, detail: Mapping[str, object]); Event.to_json() -> dict[str, object]; Event.from_json(value: Mapping[str, object]) -> Event. Event and Milestone validation accepts the legal nonterminal state INVALIDATED = "invalidated" for reversal records.
- Produces LocalProjection as a frozen dataclass with run_id: str, agent: str, machine_id: str, claim_id: str | None, state: str, outcome: str | None, branch: str, area: str, files: tuple[str, ...], candidate: Candidate | None, base_sha: str, evidence_head_sha: str, pr: int | None, parent_run_id: str | None, blocker: Blocker | None, claim_expires_at: str | None, milestones: tuple[Milestone, ...], updated_at: str, claim_released: bool, gate_inventory: tuple[str, ...], skipped_gates: tuple[str, ...], evidence_pointers: Mapping[str, tuple[str, ...]], review_rounds: int, last_summary: str | None, remote_sync: str, and warning: str | None. It also exposes to_dict() -> dict[str, object] for the later summary/publication layers; the mapping is JSON-safe and preserves the same allowlisted fields. The optional claim_id/claim_expires_at are local-only until Plan 2a binds a remote claim; files/candidate use the same validators as the remote RunProjection.
- Produces ReceiptStore(root: Path, run_id: str, *, clock: Callable[[], datetime] | None = None), with create_started(*, agent: str, machine_id: str, branch: str, area: str, base_sha: str, files: Sequence[str] = (), pr: int | None = None, candidate: Candidate | None = None, gate_inventory: Sequence[str] = (), skipped_gates: Sequence[str] = (), authorized_actions: Sequence[str] = ()) -> LocalProjection, append(*, event: str, state: None = None, evidence_head_sha: None = None, detail: Mapping[str, object] | None = None) -> Event for non-state diagnostic events only, load_events() -> tuple[Event, ...], current_projection() -> LocalProjection, write_current(projection: LocalProjection) -> None, mark_remote_lagging() -> None, mark_remote_synced() -> None, and rebuild_projection() -> LocalProjection. create_started records the preflight facts and action names for audit only; later commands never read authorized_actions as authority. Stateful events use private lock-held helpers exposed only through advance/close/invalidate/resume/review methods, so callers cannot bypass transition guards with append.
- Produces ReceiptCorrupt(ValueError) for a malformed non-final event, sequence/timestamp/schema violation, or invalid current projection. A torn final line returns the valid prefix from load_events() and stores a warning string in rebuild_projection(). It never truncates events.jsonl.
- ReceiptStore.create_started writes the initial event with state started and no remote claim; the run directory is created with mode 0o700 and files with mode 0o600.

- [ ] **Step 1: Write failing durability and torn-line tests**

Use a temporary receipt root and patch fsync through a recorder. The test must observe the exact JSONL event keys and the write order:

~~~python
def test_append_fsyncs_event_before_replacing_current(tmp_path, monkeypatch):
    store = ReceiptStore(tmp_path, "20260827T040000Z-agent-9f3a1c")
    store.create_started(
        agent="agent", machine_id="linux", branch="fix/bug", area="bug",
        base_sha="23c3551a30ac5d230f68a01b76650c27144571f5",
    )
    calls = []
    real_fsync = os.fsync
    real_replace = os.replace

    def record_fsync(fd):
        calls.append("fsync")
        return real_fsync(fd)

    def record_replace(source, target):
        calls.append("replace")
        return real_replace(source, target)

    monkeypatch.setattr(os, "fsync", record_fsync)
    monkeypatch.setattr(os, "replace", record_replace)
    store.append(event="durability-probe", state=None,
                 evidence_head_sha=None, detail={"gate": "durability"})
    assert calls.index("fsync") < calls.index("replace")
    lines = (store.directory / "events.jsonl").read_text().splitlines()
    assert json.loads(lines[-1])["seq"] == 2
    assert (store.directory / "current.json").is_file()


def test_torn_final_line_is_preserved_and_excluded(tmp_path):
    store = ReceiptStore(tmp_path, "20260827T040000Z-agent-9f3a1c")
    store.create_started(
        agent="agent", machine_id="linux", branch="fix/bug", area="bug",
        base_sha="23c3551a30ac5d230f68a01b76650c27144571f5",
    )
    events_path = store.directory / "events.jsonl"
    with events_path.open("ab") as fh:
        fh.write(b'{"seq": 2, "event": "fixed"')
    events = store.load_events()
    assert [event.seq for event in events] == [1]
    projection = store.rebuild_projection()
    assert projection.warning == "torn final event line excluded"
    assert events_path.read_bytes().endswith(b'{"seq": 2, "event": "fixed"')
~~~

- [ ] **Step 2: Run the receipt tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_receipt.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection with ImportError because ReceiptStore and Event do not exist.

- [ ] **Step 3: Implement append, lock, fsync, and atomic projection**

Create a per-run .lock and use fcntl.flock(LOCK_EX) around every mutation. For append, open events.jsonl with os.open(path, O_WRONLY | O_APPEND | O_CREAT, 0o600), serialize one compact JSON object plus a newline, loop on os.write until every byte is written, call os.fsync(fd), and close. Read existing events while holding the same lock, calculate the next sequence as the last valid sequence plus one, and reject a duplicate/non-increasing sequence. Write current.json.tmp with json.dumps(projection, sort_keys=True, indent=2), flush it, call os.fsync, use os.replace, then open the receipt directory and fsync its descriptor. The projection replacement must occur after the event fsync, never before it.

Parse events line-by-line. A line without a terminating newline is a torn candidate only when it is the final non-empty line; JSON-decode errors anywhere else raise ReceiptCorrupt. Preserve the exact bytes and report the fixed warning text above. Reject extra event fields, control characters, invalid state/evidence values, and detail values that include credentials; detail is local but still sanitized. Do not use a JSON rewrite to “repair” events.jsonl.

Use a simple projection dictionary for atomic serialization and reconstruct LocalProjection with exact immutable tuples. Implement LocalProjection.to_dict() as the JSON-safe conversion used by summary.py and publication.py. current_projection() reads current.json after validating it; rebuild_projection() folds only valid events in sequence order and appends no new event. It carries remote_sync="synced" initially, changes to "remote-lagging" only through mark_remote_lagging(), and returns to "synced" only through mark_remote_synced() after a successful remote CAS repair.

- [ ] **Step 4: Run the receipt tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_receipt.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for directory/file permissions, event sequence, fsync-before-projection ordering, atomic replacement, malformed non-final failure, torn-final preservation, and no event rewrite.

- [ ] **Step 5: Commit receipt durability**

~~~bash
git add scripts/nous/receipt.py tests/unit/scripts/test_nous_receipt.py
git commit -m "feat(nous): add crash-safe local receipts"
~~~

### Task 2: Enforce transitions, evidence-head invalidation, and resume demotion

**Files:**
- Modify: scripts/nous/receipt.py
- Modify: tests/unit/scripts/test_nous_receipt.py

**Interfaces:**
- Consumes ReceiptStore from Task 1 and RunProjection/Milestone from Plan 0.
- Produces LEGAL_TRANSITIONS for nonterminal advance targets only: started -> claimed; claimed -> reproduced; reproduced -> fixed; fixed -> reviewed; reviewed -> locally_verified; locally_verified -> published; published -> hosted_verified; hosted_verified -> merged_verified. It also produces COMPLETED_OUTCOMES = ("merged", "ready-for-human", "dry"), CANCELLATION_OUTCOME = "cancelled", TERMINAL_OUTCOMES = COMPLETED_OUTCOMES + (CANCELLATION_OUTCOME,), and close-specific terminal guards (merged only from merged_verified, dry only from started/claimed, ready-for-human/cancelled from any nonterminal). Cancellation is a distinct explicit user outcome, not a completed tick result.
- Produces advance(*, to_state: str, evidence_head_sha: str, tier: str, detail: Mapping[str, object] | None = None) -> LocalProjection. It rejects an illegal edge, a non-40-hex SHA, a local-tier remote state, or a missing causal/review/gate detail with ReceiptValidationError.
- Produces close(*, outcome: str, detail: Mapping[str, object] | None = None, blocker: Blocker | None = None, parent_run_id: str | None = None) -> LocalProjection. merged is legal only from merged_verified; dry only from started/claimed; ready-for-human retains the claim and records expiry; cancelled releases it and records the reason. For every terminal outcome, LocalProjection.state remains the last reached stage, outcome is set, and an outcome Milestone is appended. The local projection records claim_released bool and parent_run_id.
- Produces invalidate_head(*, old_sha: str, new_sha: str, affected: Sequence[str]) -> LocalProjection. It appends an invalidated event naming both SHAs and affected states, regresses current state to fixed at new_sha, keeps the published/pr binding, and never deletes prior milestones.
- Produces ReceiptStore.resume_without_local_receipt(remote: RunProjection, *, branch_exists_at_head: bool, pr_exists_at_head: bool, merged_verified: bool) -> tuple[LocalProjection, tuple[str, ...]]. It demotes every local-tier reproduced/fixed/reviewed/locally_verified milestone, returns the names in the second tuple, and creates a resumed event for the new machine. Remote-tier facts are retained only as validated branch/files/candidate/head/PR bindings; those files and candidate inputs are available to a later conflict-checked re-claim after expiry. Merged facts are retained only when merged_verified is true.

- [ ] **Step 1: Add failing transition and invalidation tests**

Add parameterized tests for every legal edge and representative illegal edges, then prove exact-head invalidation:

~~~python
def test_illegal_transition_is_rejected(store):
    store.create_started(**STARTED)
    with pytest.raises(ReceiptValidationError):
        store.advance(to_state="reviewed", evidence_head_sha=HEAD, tier="local")


def test_head_drift_invalidates_review_and_local_gate(store):
    store.create_started(**STARTED)
    details = {
        "claimed": {"claim_id": "c-a1b2c3d4e5f6"},
        "reproduced": {"reproduction": "reproduced at the pinned head"},
        "fixed": {"causal_red": "red failed", "causal_green": "green passed"},
        "reviewed": {"review_round": 1},
        "locally_verified": {"gate_results": {"unit": "pass"}, "skipped_gates": []},
        "published": {"pr": STARTED["pr"]},
        "hosted_verified": {"checks": {"required": "pass"}},
    }
    for state in ("claimed", "reproduced", "fixed", "reviewed", "locally_verified", "published", "hosted_verified"):
        store.advance(
            to_state=state, evidence_head_sha=HEAD,
            tier="remote" if state in {"published", "hosted_verified"} else "local",
            detail=details[state],
        )
    projection = store.invalidate_head(old_sha=HEAD, new_sha=NEW_HEAD,
                                       affected=("reviewed", "locally_verified", "hosted_verified"))
    assert projection.state == "fixed"
    assert projection.evidence_head_sha == NEW_HEAD
    assert projection.pr == STARTED["pr"]
    assert projection.milestones[-1].state == "invalidated"
    assert projection.milestones[-1].evidence_head_sha == NEW_HEAD


def test_resume_demotes_local_tier_but_keeps_branch_and_pr_bindings(store, remote_projection):
    projection, demoted = store.resume_without_local_receipt(
        remote_projection, branch_exists_at_head=True, pr_exists_at_head=True,
        merged_verified=False,
    )
    assert set(demoted) == {"reproduced", "fixed", "reviewed", "locally_verified"}
    assert projection.state == "claimed"
    assert projection.pr == remote_projection.pr
~~~

- [ ] **Step 2: Run focused transition tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_receipt.py -q -k 'transition or invalidat or resume or terminal' -p no:cacheprovider --no-cov
~~~

Expected: FAIL because the state guards, terminal shape, SHA invalidation, and resume demotion methods are not defined.

- [ ] **Step 3: Implement the state machine and terminal shapes**

Fold only the exact transition map above. advance first checks the current state, then validates the target tier: reproduced/fixed/reviewed/locally_verified require tier="local"; published/hosted_verified/merged_verified require tier="remote". Require detail keys reproduction for reproduced, causal_red and causal_green for fixed, review_round for reviewed, and gate_results plus skipped_gates for locally_verified. Accept INVALIDATED as an event/milestone state only for invalidate_head and resume demotion; it is not an advance target or current state. Store evidence_head_sha on both the event and milestone. Never allow advance to write merged, dry, ready-for-human, or cancelled; close owns terminal outcomes.

close appends a terminal outcome event/milestone and updates the projection atomically in one local receipt mutation while preserving the last stage in state. For ready-for-human, require a Blocker and retain the active claim with claim_expires_at in the report. For merged, require current state merged_verified, keep state=merged_verified, set outcome=merged, and mark the claim released; this is the local equivalent of the single remote terminal metadata operation Plan 2a will implement. Do not create a separate unverified merged state. For dry, allow only started/claimed, preserve that state, and record checked candidate sources. For cancelled, preserve the last nonterminal state, release the claim, and record an explicit cancellation reason; cancellation is not included in COMPLETED_OUTCOMES. Validate parent_run_id with validate_run_id.

After Task 2, public append rejects any non-None state/evidence SHA; advance, close, invalidate_head, and resume use a private `_append_stateful_locked` helper after their guards. invalidate_head appends a reversal event with detail {"old_head_sha": old_sha, "new_head_sha": new_sha, "affected": list(affected)}, retains prior milestones in history, appends one reversal milestone with state invalidated and evidence_head_sha=new_sha, and sets state=fixed. It must not clear pr or branch. advance and current_projection reject a reviewed/hosted state whose newest valid milestone SHA differs from the current evidence head.

For resume, copy the remote projection into a new local receipt, append invalidated events for each local-tier milestone, set working state claimed whenever the claim is live/retained, and retain only validated branch/head/pr metadata. If merged_verified is true, retain that terminal fact; otherwise do not synthesize local proof. The returned demotion tuple is deterministic in state order.

- [ ] **Step 4: Run transition tests and the Plan 0 compatibility suite**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_receipt.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/test_loop_bridge.py tests/unit/scripts/test_nous_backend_local.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for all receipt transition tests and all unchanged Plan 0 bridge/backend tests.

- [ ] **Step 5: Commit the receipt state machine**

~~~bash
git add scripts/nous/receipt.py tests/unit/scripts/test_nous_receipt.py
git commit -m "feat(nous): enforce receipt transitions and head freshness"
~~~

### Task 3: Add injectable read-only preflight and authorization accounting

**Files:**
- Create: scripts/nous/preflight.py
- Create: tests/unit/scripts/test_nous_preflight.py

**Interfaces:**
- Consumes CoordinationBackend, LocalMutex, Claim, Candidate, BackendUnavailable, Conflict, and ValidationError from Plan 0; consumes ReceiptStore from Tasks 1–2 only for the later CLI claim path, never from run_preflight.
- Produces ALLOWED_ACTIONS = ("coordinate", "push", "create-pr", "comment", "merge", "change-ruleset") and Authorization(allowed: frozenset[str]) with from_names(names: Iterable[str]) -> Authorization and allows(action: str) -> bool. Unknown action names raise ValidationError; no token/credential field exists.
- Produces WorkspaceFacts(clean: bool, isolated: bool, root: str) and GateInventory(available: tuple[str, ...], unavailable: tuple[str, ...], skipped: tuple[str, ...]).
- Produces PreflightProbes protocol with fetch_base() -> str, workspace() -> WorkspaceFacts, gates() -> GateInventory, backend_reachable() -> bool, and reconcile_prior_runs() -> tuple[str, ...]; every method is observational, tests provide a fake, and Plan 2a’s guarded GitIO-backed probe will implement it without repairing or mutating a run.
- Produces PreflightResult(base_sha: str, workspace: WorkspaceFacts, gates: GateInventory, reconciled_runs: tuple[str, ...], authorization: Authorization, mode: str, remote_run_created: bool, ready_for_human: str | None).
- Produces run_preflight(*, agent: str, backend: CoordinationBackend | LocalMutex, probes: PreflightProbes, authorization: Authorization, mode: str) -> PreflightResult. It verifies base freshness, clean isolation, backend reachability, mode in ("local", "remote-required"), and observational prior-run reconciliation. It is read-only: it calls no mutation method, creates no receipt or lock, and never calls backend.claim or creates a remote projection. The explicit Authorization argument is the only source of permitted action names.
- Produces require_action(source: Authorization | PreflightResult, action: str) -> None, which reads either the supplied Authorization or source.authorization and raises AuthorizationRequired (a typed ValidationError) before the corresponding mutation when the action is absent. Service functions may therefore enforce the current request directly without reconstructing a PreflightResult.

- [ ] **Step 1: Write failing preflight tests**

Use a fake read-only probe whose calls are recorded and a fake backend. Cover clean success, dirty/unisolated refusal, backend outage, unknown mode, independent authorization, and the key invariant that no receipt, remote claim, or run projection is created:

~~~python
def test_preflight_records_facts_without_creating_remote_run(fake_probe, fake_backend, tmp_path):
    before = tuple(tmp_path.iterdir())
    result = run_preflight(
        agent="agent", backend=fake_backend, probes=fake_probe,
        authorization=Authorization.from_names(["coordinate"]), mode="local",
    )
    assert result.base_sha == "23c3551a30ac5d230f68a01b76650c27144571f5"
    assert result.remote_run_created is False
    assert fake_backend.claim_calls == []
    assert fake_probe.calls == ["fetch_base", "workspace", "gates", "backend_reachable", "reconcile_prior_runs"]
    assert tuple(tmp_path.iterdir()) == before


def test_missing_merge_permission_stops_before_merge():
    result = successful_result(allowed=("coordinate", "push"))
    with pytest.raises(AuthorizationRequired):
        require_action(result, "merge")


def test_require_action_accepts_the_injected_authorization_directly():
    with pytest.raises(AuthorizationRequired):
        require_action(Authorization.from_names(("coordinate",)), "merge")
~~~

- [ ] **Step 2: Run preflight tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_preflight.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because preflight protocols, authorization, and result types are absent.

- [ ] **Step 3: Implement preflight checks and action boundary**

Call probe methods in this order: fetch_base, workspace, gates, backend_reachable, reconcile_prior_runs. Validate the fetched base with validate_sha. Reject dirty or non-isolated workspaces with ready_for_human="workspace-not-clean-or-isolated"; reject a false reachability result with BackendUnavailable; reject local/remote-required mode mismatch at this layer with ValidationError. Preserve every unavailable and skipped gate exactly as supplied. Call no mutating backend method and do not instantiate ReceiptStore or create any path.

Return PreflightResult with remote_run_created=False and the injected Authorization unchanged. The caller, after it has validated its branch/area/files and chosen exactly one run ID, creates the receipt and records the preflight facts; run_preflight itself never writes them. require_action accepts either a PreflightResult or the current Authorization object and checks membership independently for each command; authorization to coordinate does not imply push, create-pr, comment, merge, or change-ruleset.

Use the same result object for Plan 2a mode selection. That phase may replace the injected probe implementation but must keep this call order, field names, and authorization semantics.

- [ ] **Step 4: Run preflight tests to verify the green result**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_preflight.py -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for base SHA validation, clean/isolated checks, backend outage, mode validation, gate skip preservation, no remote claim creation, and independent action authorization.

- [ ] **Step 5: Commit preflight**

~~~bash
git add scripts/nous/preflight.py tests/unit/scripts/test_nous_preflight.py
git commit -m "feat(nous): add live preflight authorization boundary"
~~~

### Task 4: Render evidence-only reports and expose the local-mode CLI

**Files:**
- Create: scripts/nous/summary.py
- Create: scripts/nous_run.py
- Create: tests/unit/scripts/test_nous_summary.py
- Create: tests/unit/scripts/test_nous_run_cli.py

**Interfaces:**
- Consumes Event, LocalProjection, ReceiptStore, COMPLETED_OUTCOMES, CANCELLATION_OUTCOME, TERMINAL_OUTCOMES, PreflightResult, Authorization, LocalMutex/LocalBackend, Candidate, Claim, and typed errors from Tasks 1–3 and Plan 0.
- Produces render_terminal_report(events: Sequence[Event], projection: Mapping[str, object]) -> str, render_status_json(projection: Mapping[str, object]) -> str, and render_pr_body(events: Sequence[Event], projection: Mapping[str, object]) -> str. All output is derived from event states, exact SHAs, gate results, verbatim skip list, review-round detail, blockers, and current evidence_head_sha; it never adds a success claim for an absent event.
- Produces sanitize_detail(detail: Mapping[str, object]) -> Mapping[str, object] and SummaryValidationError(ValueError). It rejects raw stdout, traceback, prompt/user text, credentials, control characters, and secret-shaped values; it does not yet add the Plan 2b slash-trigger guard.
- Produces build_parser() -> argparse.ArgumentParser, main(argv: Sequence[str] | None = None, *, backend: CoordinationBackend | LocalMutex | None = None, probes: PreflightProbes | None = None, receipt_root: Path | None = None, authorization: Authorization | None = None) -> int, and map_error(exc: Exception) -> int. An injected `authorization` is explicit and takes precedence over parsed flags; when it is omitted, the command’s repeatable `--authorize ACTION` values are converted with Authorization.from_names().
- The CLI parser exposes exactly: preflight --agent [--authorize ACTION ...] [--json]; claim --agent --branch --area [--files] [--candidate-summary --candidate-source] [--authorize ACTION ...]; renew --run-id [--authorize ACTION ...]; advance --run-id --to --evidence-head [--pr] [--authorize ACTION ...]; publish --run-id --pr; verify-merge --run-id; close --run-id --outcome [--blocker] [--parent-run-id] [--authorize ACTION ...]; resume --run-id [--json]; status [--run-id] [--json]; list [--json]; reconcile [--json]; gc. `--authorize` uses argparse action="append", so each listed command accepts the flag more than once; read-only status/list do not require it. Plans 2a and 2b extend the same repeatable option to bootstrap/cutover and publish/verify-merge/merge-related mutations, with their own command-specific action checks.
- Plan 1 implements preflight, claim, renew, advance through locally_verified, close, status, and list in local mode. The CLI rejects manually supplied published/hosted_verified/merged_verified targets: Plan 2b's evidence-deriving services own them. publish, verify-merge, resume, reconcile, and gc return BackendUnavailable (exit 3) with a machine-readable error until Plans 2a/2b supply remote services; this is an explicit capability boundary, not a local-only fallback.
- Claim validates agent/branch/area/files, invokes read-only run_preflight after those values are known, requires the injected/parsed `coordinate` action, creates exactly one run ID and one started receipt only after preflight passes, records the returned base/gate/skip facts and current action names in that receipt, then calls LocalMutex.claim_legacy with ttl_seconds=10_800 and appends claimed. Stored action names are audit data and grant nothing to later invocations. Local claim metadata has no remote projection. renew requires coordinate and calls LocalMutex.heartbeat_legacy keyed by branch; advance requires coordinate; close requires merge for outcome merged and coordinate for dry/ready-for-human/cancelled. Local conflict maps to exit 2.
- map_error maps Conflict and ClaimLost to 2, BackendUnavailable to 3, ValidationError/ReceiptValidationError/SummaryValidationError to 4, argparse usage to 1, and all other exceptions to 1 without printing a traceback.

- [ ] **Step 1: Write failing summary and CLI contract tests**

Add tests that prove a rendered report cannot claim a state not present in events and that the parser/exit map are stable:

~~~python
def test_terminal_report_lists_only_recorded_states_and_skips(tmp_path):
    events = (
        Event(1, NOW, "preflight", "started", HEAD, {"skipped": ["e2e"]}),
        Event(2, NOW, "reproduced", "reproduced", HEAD, {"gate": "reproduction"}),
    )
    body = render_terminal_report(events, {"state": "reproduced", "evidence_head_sha": HEAD})
    assert "reproduced" in body and "e2e" in body
    assert "merged" not in body


def test_local_claim_runs_read_only_preflight_and_uses_three_hour_ttl(
    fake_local_backend, fake_probe, tmp_path
):
    rc = main(
        ["claim", "--agent", "agent", "--branch", "fix/bug", "--area", "bug",
         "--authorize", "coordinate"],
        backend=fake_local_backend, probes=fake_probe, receipt_root=tmp_path,
    )
    assert rc == 0
    assert fake_local_backend.claim_legacy_calls[0]["ttl_seconds"] == 10_800
    assert len(list(tmp_path.glob("*/events.jsonl"))) == 1


def test_injected_authorization_blocks_claim_before_local_mutation(
    fake_local_backend, fake_probe, tmp_path
):
    rc = main(
        ["claim", "--agent", "agent", "--branch", "fix/bug", "--area", "bug"],
        backend=fake_local_backend, probes=fake_probe, receipt_root=tmp_path,
        authorization=Authorization.from_names(()),
    )
    assert rc == 4
    assert fake_local_backend.claim_legacy_calls == []


def test_authorize_flag_is_repeatable():
    args = build_parser().parse_args([
        "claim", "--agent", "agent", "--branch", "fix/bug", "--area", "bug",
        "--authorize", "coordinate", "--authorize", "push",
    ])
    assert args.authorize == ["coordinate", "push"]


@pytest.mark.parametrize(("exc", "expected"), [
    (Conflict("overlap"), 2), (BackendUnavailable("offline"), 3),
    (ValidationError("bad input"), 4), (RuntimeError("bug"), 1),
])
def test_error_code_contract(exc, expected):
    assert map_error(exc) == expected
~~~

- [ ] **Step 2: Run summary and CLI tests to verify the failure**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py -q -p no:cacheprovider --no-cov
~~~

Expected: FAIL during collection because summary functions and scripts/nous_run.py do not exist.

- [ ] **Step 3: Implement event-only rendering and command dispatch**

Render a stable text report with sections for current state, evidence head, recorded milestones, gates, skipped gates, review rounds, blocker, and outcome. Iterate events rather than accepting prose fields; include only detail keys from an allowlist (gate, result, skip, review_round, blocker_kind, blocker_detail, candidate_sources, old_head_sha, new_head_sha). Render JSON with sort_keys=True and no local path/credential fields. render_pr_body is the same event projection with a marker added by Plan 2b; do not inspect GitHub text here.

Build the parser with required flags matching the spec and add `--authorize ACTION` with action="append" to preflight, claim, renew, advance, and close. In local mode, instantiate or use the injected LocalMutex and ReceiptStore. Claim must validate agent/branch/area/files, invoke run_preflight with the explicit Authorization before any receipt or lease mutation, generate run_id exactly once after preflight succeeds, create exactly one started receipt carrying the returned base/gate/skip facts and current action names, call LocalMutex.claim_legacy, then append claimed. `require_action(result, "coordinate")` runs before claim, renew, or local advance; the Plan 1 CLI allowlists claimed/reproduced/fixed/reviewed/locally_verified and rejects remote evidence states even though ReceiptStore exposes guarded methods for later services. close selects `merge` only for outcome merged and `coordinate` for dry, ready-for-human, and cancelled before calling ReceiptStore.close and releasing the local lease only for merged, dry, or cancelled, retaining it for ready-for-human. The Plan 2a/2b extensions add the same repeatable `--authorize` flag to bootstrap, cutover, publish, verify-merge, and merge-related mutations and call require_action with the current Authorization or PreflightResult immediately before each mutation. Status/list are observational and must not create missing board storage. Remote-dependent commands raise BackendUnavailable rather than silently falling back.

main catches only expected exceptions at the outer boundary, writes JSON when --json is supplied, and emits concise stderr without exception details that could contain secrets. Do not call sys.exit from command handlers; return the integer.

- [ ] **Step 4: Run summary/CLI tests and the full isolated script gate**

Run:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py -q -p no:cacheprovider --no-cov
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
~~~

Expected: PASS for evidence-only summaries, parser flags, local three-hour TTL, no local fallback for remote commands, JSON output, and all Plan 0 tests.

- [ ] **Step 5: Commit summaries and CLI skeleton**

~~~bash
git add scripts/nous/summary.py scripts/nous_run.py tests/unit/scripts/test_nous_summary.py tests/unit/scripts/test_nous_run_cli.py
git commit -m "feat(nous): add receipts preflight summaries and CLI"
~~~

## Plan-level verification and acceptance evidence

Run after all task commits:

~~~bash
PYTHONPATH=. pytest tests/unit/scripts/ --confcutdir=tests/unit/scripts -q -p no:cacheprovider --no-cov
python3 -m compileall -q scripts/nous scripts/nous_run.py
git diff --check
git status --short
~~~

Expected: the isolated script tests pass, compileall emits no output, diff check is silent, and git status --short is clean after the task commits. Acceptance evidence is a durable fsynced event prefix with torn-final warning, every legal/illegal transition enforced, exact-head invalidation regression to fixed, resume demotion of all local-tier milestones, preflight action separation, and local CLI exit/TTL contracts. No Git or GitHub capability is claimed until Plan 2a and Plan 2b.
