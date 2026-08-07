# Tool-Coverage Benchmark Plan 1: harbor_common + agent-project-management-v1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared `evals/harbor_common/` module and the first new Harbor task `agent-project-management-v1` (capability 14: create_project, list_projects, add_document_to_project, create_project_note, list_project_documents), calibration-verified end to end.

**Architecture:** Clone the `agent-direct-project-action-v1` pattern (graph-level adapter driving `compile_agent_graph`, HITL resume, independent psycopg verifier). Hoist byte-identical/near-identical pieces into `harbor_common` first, consume them from the new task. Verification without Docker: `verify.py` runs standalone against calibration fixtures via `BENCHMARK_CALIBRATION_FIXTURE`.

**Tech Stack:** Python 3.11, psycopg 3 (dict_row), LangGraph agent graph from pinned backend, Harbor 0.6.6 task schema 1.2, docker-compose w/ Squid egress proxy.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-08-07-tool-coverage-benchmark-design.md` — binding.
- Spec-file format: `evals/specs/<task>/{task.md,environment.md,harness.md}`, line 1 `Status: approved`, `Label:` paragraphs, NO markdown headings (match existing specs verbatim in label order — see `evals/specs/agent-direct-project-action-v1/`).
- Reward protocol: verify.py exit 0 → reward 1; exit 10 → reward 0; anything else → infra failure, no reward file.
- Fixed UUID block for this task: `00000000-0000-0000-0000-000000000501` … `0507` (next free range after stream task's `…04xx`).
- `EXPECTED_INSTRUCTION` must be byte-identical in instruction.md, run_agent.py, verify.py.
- Existing 3 tasks are NOT modified (digest-pinned). `harbor_common` is consumed only by new tasks.
- Impl caps are ground truth (e.g. `list_projects` impl cap 50 — `tools_impl.py:2062`), not wrapper caps.
- New-file basenames must not collide with pytest collection: name adapter `run_agent.py` is unavoidable (Harbor convention) — it lives under `environment/` which pytest doesn't collect; verifier stays `verify.py` under `tests/` with no `test_` prefix. Do NOT create files starting `test_` inside evals task dirs except `test.sh`.
- Commits: small, one per task, conventional format.
- Work on branch `feat/tool-coverage-bench-plan1` off develop (create in Task 0).

---

### Task 0: Branch

**Files:** none

- [ ] **Step 1:** `cd /root/rag-verify && git checkout -b feat/tool-coverage-bench-plan1`
  (develop already carries the design-doc commit `2d2a94b`; branch includes it.)

---

### Task 1: harbor_common — pure-python helpers

**Files:**
- Create: `evals/harbor_common/__init__.py` (empty)
- Create: `evals/harbor_common/serialization.py`
- Create: `evals/harbor_common/envelope.py`
- Test: `evals/harbor_common/selftest.py` (plain script, NOT pytest-collected; run with `python`)

**Interfaces:**
- Produces: `json_safe(obj) -> Any` (JSON-encodable deep copy); `class InfrastructureFailure(RuntimeError)`; `utc_now() -> str` (ISO-8601 UTC, `Z` suffix); `run_verifier_main(benchmark_id: str, gate_fn, report_extra_fn=None) -> int` (returns 0/10/2, writes `/logs/verifier/audit.json` — path overridable via env `VERIFIER_REPORT_PATH` for local testing); `load_inputs(default_evidence_path: str, live_reader=None) -> dict` (calibration switch on `BENCHMARK_CALIBRATION_FIXTURE`).

- [ ] **Step 1:** Copy `json_safe` + `utc_now` verbatim from `evals/agent-direct-project-action-v1/environment/run_agent.py:45-85` into `serialization.py` (this is the canonical variant per the drift audit; add the `datetime` branch from the stream task's `run_agent.py:62-80`).

- [ ] **Step 2:** Write `envelope.py`:

```python
"""Shared adapter/verifier envelopes for Harbor eval tasks.

Consumed only by tasks added after 2026-08-07; the three original tasks
are digest-pinned and keep their inline copies.
"""
import json
import os
import sys
import traceback


class InfrastructureFailure(RuntimeError):
    """Environment/harness defect — exit 70 (adapter) / 2 (verifier), no reward."""


def load_inputs(default_evidence_path, live_reader=None):
    """Return {'evidence': ..., 'state': ...}.

    BENCHMARK_CALIBRATION_FIXTURE set -> load that JSON instead of live state.
    Fixture envelope is unified: {"evidence": {...}, "state": {...}}.
    live_reader() supplies the independent state read for live runs.
    """
    fixture = os.environ.get("BENCHMARK_CALIBRATION_FIXTURE")
    if fixture:
        with open(fixture, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if "evidence" not in data:
            raise InfrastructureFailure(
                "calibration fixture missing 'evidence' key (unified envelope required)"
            )
        return {
            "evidence": data["evidence"],
            "state": data.get("state", {}),
            "input_source": fixture,
        }
    with open(default_evidence_path, "r", encoding="utf-8") as fh:
        evidence = json.load(fh)
    state = live_reader() if live_reader else {}
    return {"evidence": evidence, "state": state, "input_source": "live"}


def run_verifier_main(benchmark_id, gate_fn, report_extra_fn=None):
    """0 = pass, 10 = scoreable failure, 2 = verifier infrastructure error."""
    report_path = os.environ.get("VERIFIER_REPORT_PATH", "/logs/verifier/audit.json")
    try:
        inputs = load_inputs(
            os.environ.get("EVIDENCE_PATH", "/logs/agent/evidence.json"),
            live_reader=gate_fn.live_reader if hasattr(gate_fn, "live_reader") else None,
        )
        failures = gate_fn(inputs["evidence"], inputs["state"])
        report = {
            "benchmark_id": benchmark_id,
            "input_source": inputs["input_source"],
            "passed": not failures,
            "failures": failures,
        }
        if report_extra_fn:
            report.update(report_extra_fn(inputs["evidence"], inputs["state"]))
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
        print(json.dumps(report, sort_keys=True))
        return 0 if not failures else 10
    except Exception:  # noqa: BLE001 - anything unexpected is infra, not reward 0
        err = {"benchmark_id": benchmark_id, "verifier_error": traceback.format_exc()}
        print(json.dumps(err), file=sys.stderr)
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as fh:
                json.dump(err, fh, indent=2)
        except OSError:
            pass
        return 2
```

- [ ] **Step 3:** Write `selftest.py` exercising: `json_safe` on nested dict w/ datetime; `load_inputs` fixture path (write temp fixture, assert envelope + missing-evidence raises); `run_verifier_main` with a gate returning `[]` → 0, `["boom"]` → 10, raising gate → 2, using `VERIFIER_REPORT_PATH` in a temp dir. Plain asserts, `print("selftest ok")` at end.

- [ ] **Step 4:** Run: `cd /root/rag-verify && python evals/harbor_common/selftest.py` → `selftest ok`.

- [ ] **Step 5:** Commit: `feat(evals): add harbor_common serialization + envelope helpers`

---

### Task 2: harbor_common — network boundary + proxy + test.sh templates

**Files:**
- Create: `evals/harbor_common/network.py`
- Create: `evals/harbor_common/templates/proxy/Dockerfile` (byte-copy of `evals/agent-direct-project-action-v1/environment/proxy/Dockerfile`)
- Create: `evals/harbor_common/templates/proxy/entrypoint.sh` (byte-copy of `.../proxy/entrypoint.sh`)
- Create: `evals/harbor_common/templates/test.sh` (copy of `evals/agent-direct-project-action-v1/tests/test.sh`)

**Interfaces:**
- Produces: `async validate_network_boundary(model_endpoint: str, extra_probes: dict[str, callable] = None) -> dict` — parameterized version of `evals/agent-direct-project-action-v1/environment/run_agent.py:109-164`: raw socket to 1.1.1.1:443 must FAIL, model endpoint via proxy must answer any HTTP status, `https://example.com/` must be 403 (incl. `httpx.ProxyError` "403"-in-message branch); `extra_probes` maps key→async callable returning bool, results merged into the dict.

- [ ] **Step 1:** Port `validate_network_boundary` from `agent-direct-project-action-v1/environment/run_agent.py:109-164`, lifting the three probes; keep failure semantics (raise `InfrastructureFailure` on boundary violation).
- [ ] **Step 2:** `cp` the three template files; `chmod +x` on `entrypoint.sh`/`test.sh`. Verify byte-equality: `md5sum evals/harbor_common/templates/proxy/entrypoint.sh evals/agent-direct-project-action-v1/environment/proxy/entrypoint.sh` → same hash.
- [ ] **Step 3:** Commit: `feat(evals): add harbor_common network validator + proxy/test.sh templates`

---

### Task 3: harbor_common — DB bootstrap/seeding + state + ATIF

**Files:**
- Create: `evals/harbor_common/db.py`
- Create: `evals/harbor_common/trajectory.py`

**Interfaces:**
- Produces: `async bootstrap_schema()` (Base.metadata.create_all — copy `agent-direct-project-action-v1/environment/run_agent.py:88-106` incl. Alembic-broken rationale comment); `async seed_tenant(org_id, user_id, workspace_id, name_prefix, email) -> None` (generalize `.../run_agent.py:167-216`: initialize_encryption + DATA key + Organization/User/Workspace inserts); `initial_agent_state(instruction: str, thread_id: str, **overrides) -> dict` (the ~25-key LangGraph state dict from `.../run_agent.py:260-290`, overrides merged last); `collect_model_usage(messages) -> dict` and `final_assistant_message(messages) -> dict` (verbatim `.../run_agent.py:322-344`); `build_atif_trajectory(evidence, benchmark_id, thread_id, extra_steps_hook=None) -> dict` (from `.../run_agent.py:347-446`, HITL step injection moved behind `extra_steps_hook`).
- Consumes: `serialization.json_safe`, `envelope.InfrastructureFailure`.

- [ ] **Step 1:** Port each function per refs above. Import backend models lazily inside functions (module import must not require DB).
- [ ] **Step 2:** Syntax/import check only (DB-dependent, no live DB here): `python -c "import ast,sys; ast.parse(open('evals/harbor_common/db.py').read()); ast.parse(open('evals/harbor_common/trajectory.py').read()); print('ok')"`
- [ ] **Step 3:** Commit: `feat(evals): add harbor_common db seeding + ATIF trajectory builders`

---

### Task 4: agent-project-management-v1 — specs triple + instruction + task.toml

**Files:**
- Create: `evals/specs/agent-project-management-v1/task.md`
- Create: `evals/specs/agent-project-management-v1/environment.md`
- Create: `evals/specs/agent-project-management-v1/harness.md`
- Create: `evals/agent-project-management-v1/instruction.md`
- Create: `evals/agent-project-management-v1/task.toml`
- Create: `evals/agent-project-management-v1/.gitignore` (copy from `evals/agent-direct-project-action-v1/.gitignore`)

**Interfaces:**
- Produces: `EXPECTED_INSTRUCTION` (exact string below) consumed by Tasks 5-6.

Canonical instruction (single line, byte-exact everywhere):

```
Create a research project named "Tool Coverage Study", then add the pre-loaded document titled "Seed Paper" to it, create a note in it titled "Kickoff" with content "Track tool coverage benchmark progress.", and finally list the project's documents and confirm what the project now contains.
```

Trajectory this forces: `create_project` (HITL) → `list_projects` or direct id reuse → `add_document_to_project` (HITL) → `create_project_note` (HITL) → `list_project_documents` → final summary. Seeded world: 1 document ("Seed Paper", UUID `…0505`) NOT in any project.

- [ ] **Step 1:** Write the specs triple following `evals/specs/agent-direct-project-action-v1/` label order exactly (task.md 9 labels: Status/Capability/Request/Initial conditions/Why this requires the capability/Pass iff/Verifier/Verifier evidence/Accepted alternatives; environment.md: Status/Dependencies/Backend contracts/Data/Isolation/Fidelity limits; harness.md: Status/Entrypoint/Source/Preserved behavior/Adapter/Session/Credentials/Recorded evidence/Reconstruction differences). Pass iff (semicolon-joined): exactly one collection row named "Tool Coverage Study" owned by the seeded workspace; exactly one collection_documents link to document `…0505`; exactly one project_notes row titled "Kickoff" with the exact content; three HITL interrupts approved in order with no mutation before each approval; list_project_documents executed successfully returning the linked document; final assistant message names the project and the document; termination_reason completed.
- [ ] **Step 2:** Write `instruction.md` = the canonical instruction, single line.
- [ ] **Step 3:** Write `task.toml` cloning `evals/agent-direct-project-action-v1/task.toml` key-for-key; change: `[task].name = "goodwiinz/agent-project-management-v1"`, description, keywords `["langgraph","projects","notes","hitl","tools"]`, `[metadata].benchmark_id = "agent-project-management-v1"`, `source`/`source_revision` = current develop HEAD sha at implementation time (`git rev-parse HEAD`), `agent_revision` likewise, artifacts unchanged (`/logs/agent/evidence.json`, `/logs/agent/trajectory.json`).
- [ ] **Step 4:** Commit: `feat(evals): agent-project-management-v1 specs, instruction, task manifest`

---

### Task 5: agent-project-management-v1 — environment/

**Files:**
- Create: `evals/agent-project-management-v1/environment/Dockerfile`
- Create: `evals/agent-project-management-v1/environment/docker-compose.yaml`
- Create: `evals/agent-project-management-v1/environment/proxy/` (copy both files from `evals/harbor_common/templates/proxy/`)
- Create: `evals/agent-project-management-v1/environment/run_agent.py`

**Interfaces:**
- Consumes: everything from Tasks 1-3 (`from evals.harbor_common.envelope import InfrastructureFailure`, etc. — image must `COPY evals/harbor_common /app/evals/harbor_common` so imports resolve under PYTHONPATH=/app).
- Produces: `/logs/agent/evidence.json` with keys: common envelope (schema_version "1.0", benchmark_id, source_revision, agent_revision, started_at, completed_at, instruction, synthetic_actor, network_boundary, database, messages, final_assistant_message, termination_reason, model_usage, elapsed_ms) + task extras `interrupts` (list of {tool, args, approved_at}), `tool_executions` (list of {tool, status, result_keys}), `milestones` (ordered list).

- [ ] **Step 1:** Dockerfile = clone `agent-direct-project-action-v1/environment/Dockerfile` (base image + digest comment, numpy repair, COPY backend/, chmod/chown, ENV, ENTRYPOINT []); add line `COPY evals/harbor_common /app/evals/harbor_common` before the run_agent COPY; COPY path points at this task's run_agent.py.
- [ ] **Step 2:** docker-compose.yaml = clone direct-project's (main + postgres + egress-proxy, two networks, same shared env incl. tracing-off/retry/pool vars, `COHERE_API_KEY=""`, `DO_KB_API_TOKEN=""`, `REDIS_URL=""`).
- [ ] **Step 3:** run_agent.py: module constants (BENCHMARK_ID, SOURCE_REVISION, AGENT_REVISION, EXPECTED_INSTRUCTION, UUIDs `…0501` org / `…0502` user / `…0503` workspace / `…0504` thread / `…0505` seed document); import harbor_common helpers; `seed_database()` = `seed_tenant(...)` + insert one Document row (title "Seed Paper", org-owned, `is_deleted=False`, minimal content_text) and assert zero collections pre-exist; drive graph exactly like `agent-direct-project-action-v1/environment/run_agent.py:452-521` but resume **three** interrupts in sequence (loop: astream until interrupt or done; on interrupt record + `Command(resume={"confirmed": True})`); record milestones `interrupt:<tool>` / `approval:<tool>` / `<tool>_success` / `final_assistant_message`; evidence + `build_atif_trajectory(..., extra_steps_hook=hitl_steps)`; `async_main` clone with exit 70 envelope.
- [ ] **Step 4:** Syntax check: `python -m py_compile evals/agent-project-management-v1/environment/run_agent.py` (full import needs backend deps — compile check only here).
- [ ] **Step 5:** Commit: `feat(evals): agent-project-management-v1 environment + adapter`

---

### Task 6: agent-project-management-v1 — verifier + calibration (TDD core)

**Files:**
- Create: `evals/agent-project-management-v1/tests/verify.py`
- Create: `evals/agent-project-management-v1/tests/test.sh` (copy template)
- Create: `evals/agent-project-management-v1/tests/calibration/pass.json`
- Create: `evals/agent-project-management-v1/tests/calibration/wrong-premature-mutation.json`

**Interfaces:**
- Consumes: `run_verifier_main`, `load_inputs` from harbor_common (verifier imports via `sys.path.insert(0, "/app")` fallback to repo root for local runs).
- Produces: exit 0/10/2 per reward protocol.

- [ ] **Step 1 (failing test):** Write BOTH calibration fixtures FIRST, unified envelope `{"evidence": {...}, "state": {...}}`. `pass.json`: evidence with correct instruction/revisions/boundary, three interrupts in order (create_project → add_document_to_project → create_project_note), milestones ordered, tool_executions all success; state: `collections` = 1 row (name "Tool Coverage Study", workspace `…0503`, `is_deleted": false`), `collection_documents` = 1 link (`…0505`), `project_notes` = 1 row ("Kickoff", exact content), `documents` = 1. `wrong-premature-mutation.json`: identical except milestone order shows `create_project_success` BEFORE `approval:create_project` (mutation before approval).
- [ ] **Step 2:** Run verifier against both — expect FAILURE (verify.py doesn't exist): `BENCHMARK_CALIBRATION_FIXTURE=evals/agent-project-management-v1/tests/calibration/pass.json python evals/agent-project-management-v1/tests/verify.py` → error.
- [ ] **Step 3:** Write verify.py: constants (same triple + UUIDs + EXPECTED_INSTRUCTION); `objective_failures(evidence, state) -> list[str]` gates: identity triple; boundary keys all true; exactly 3 interrupts, exact tool order, args (`name == "Tool Coverage Study"`, document `…0505`, note title/content exact); per-tool milestone ordering `interrupt:<t>` < `approval:<t>` < `<t>_success`; no mutation before approval (for each destructive tool, its `_success` milestone index > its `approval:` index); state rows exactly as in pass fixture (count + field equality); `list_project_documents` execution present, success, and its result includes document `…0505`; final message mentions "Tool Coverage Study" and "Seed Paper", no dangling tool_calls; `termination_reason == "completed"`. Live reader (used only in-container): psycopg dict_row queries on `collections`/`collection_documents`/`project_notes`/`documents` cloned from `agent-direct-project-action-v1/tests/verify.py:29-58`. `main()` = `run_verifier_main(BENCHMARK_ID, objective_failures, report_extra_fn=db_snapshot)`; `sys.exit(main())`.
- [ ] **Step 4:** Run both calibrations locally:
  `VERIFIER_REPORT_PATH=/tmp/claude-0/-root/b735c00d-4bdf-482f-8ffb-4faae420589f/scratchpad/audit.json BENCHMARK_CALIBRATION_FIXTURE=evals/agent-project-management-v1/tests/calibration/pass.json python evals/agent-project-management-v1/tests/verify.py; echo "exit=$?"` → `exit=0`; same with `wrong-premature-mutation.json` → `exit=10`. Both MUST discriminate before commit.
- [ ] **Step 5:** Commit: `feat(evals): agent-project-management-v1 verifier + calibration fixtures`

---

### Task 7: Docs + manifest/baseline skeletons + README

**Files:**
- Modify: `evals/AGENT_FLOW_BASELINE.md` (section `### 14. Project management` → promote from roadmap stub to full gated-format spec section: Preconditions / Objective gates w/ file:line anchors / Semantic gate: N/A (counts as pass) / Coverage note / Status: task built, awaiting baseline run. Roadmap table row 14 tier `next` → note "task landed". Do NOT touch gated-suite membership (stays 1-3) — membership changes only with recorded run evidence.)
- Create: `evals/source-manifests/agent-flow-2026-08-07-tools.json` (schema per existing file: schema_version, suite `"nous-agent-tools-v1"`, recorded_at `_filled at run time_` → use empty string + comment key, repository_revision/agent_revision = HEAD sha, harbor_version "0.6.6", harness block w/ files+sha256 incl. harbor_common files, digest_algorithm string verbatim from existing manifest, task_digests: `{"agent-project-management-v1": "<computed>"}`, invalidation_rule verbatim)
- Create: `evals/baselines/agent-flow-2026-08-07-tools.json` (skeleton: aggregate zeroed, `verifier_calibration: {"agent-project-management-v1": {"pass": 1, "wrong-premature-mutation": 0}}`, `benchmarks: []`, evidence block noting no run recorded yet)
- Modify: `evals/README.md` (add row to task table + note harbor_common)

- [ ] **Step 1:** Compute task digest: `cd /root/rag-verify && find evals/agent-project-management-v1 -type f ! -path '*__pycache__*' -exec shasum -a 256 {} + | sed 's| /root/rag-verify/| |' | sort | shasum -a 256` (repo-relative paths; verify sed produces relative paths before trusting output). Same aggregate method over `evals/harbor_common/**` for the harness block addition.
- [ ] **Step 2:** Write the three JSON/MD updates per file list.
- [ ] **Step 3:** Validate JSON: `python -c "import json; json.load(open('evals/source-manifests/agent-flow-2026-08-07-tools.json')); json.load(open('evals/baselines/agent-flow-2026-08-07-tools.json')); print('ok')"`
- [ ] **Step 4:** Commit: `docs(evals): promote capability 14 to gated spec; manifest+baseline skeletons for tools suite`

---

### Task 8: Final verification + PR

- [ ] **Step 1:** Re-run: harbor_common selftest, both calibration exits, py_compile on run_agent.py + verify.py, JSON validation. All green.
- [ ] **Step 2:** `git log --oneline develop..HEAD` — review commit list; push branch; open PR to develop titled `feat(evals): tool-coverage benchmark — harbor_common + agent-project-management-v1 (plan 1/4)`, body: summary, test plan (calibration discrimination evidence, what needs a real Harbor run), link design doc, note follow-on plans.

---

## Follow-on plans (not in this document)

- Plan 2: tasks 2 (writing) + 6 (kb-retrieval + summarize) — reuse rag mock pattern + judge.
- Plan 3: tasks 3 (KG/Neo4j) + 4 (memory) — new Neo4j fixture.
- Plan 4: tasks 1 (arXiv double), 7 (E2B double spike-first), 8 (connectors).

## Self-review notes

- Spec coverage: plan 1 delivers common module + capability 14 + doc/manifest scaffolding; remaining spec sections explicitly deferred to plans 2-4 (listed above).
- Interface consistency: `run_verifier_main(benchmark_id, gate_fn, report_extra_fn)` used identically in Tasks 1 and 6; `InfrastructureFailure` shared; fixture envelope `{"evidence","state"}` consistent between Tasks 1 and 6.
- No placeholders: copy-sources cite exact file:line of existing audited code; new code given in full or as complete behavioral gate lists.
