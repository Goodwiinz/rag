# Project Skills and Tool Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a versioned, project-scoped, instructions-only skill catalog with staged approval, and replace scattered agent tool-name policy sets with a descriptor-backed registry while preserving current tool behavior.

**Architecture:** Keep tool handlers and schemas code-owned in a code-first registry. Persist skill identities, immutable versions, approval requests, scanner findings, and transport-neutral runtime snapshots in PostgreSQL. At turn start, freeze the enabled tool descriptors and approved project skill versions; expose only a compact skill catalog to the model and load exact frozen instructions on demand through a read-only tool.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PostgreSQL JSONB, LangGraph/LangChain tools, Next.js/React, TanStack Query, TypeScript, Vitest, pytest.

**Design source:** `docs/plans/2026-07-19-project-skills-tool-registry-design.md`

---

## Non-negotiable invariants

- Existing tool names, LangChain schemas, lazy imports, test patch seams, timeout behavior, retry behavior, HITL confirmation behavior, intent bindings, and subgraph bindings remain behaviorally identical during registry migration.
- `ALL_TOOLS` remains import-compatible but is generated from registry descriptors; it is not an independently maintained list.
- Descriptor metadata is server-owned. The database never supplies Python import paths, handler names, or executable payloads.
- Project skills contain only canonical `SKILL.md` text. No scripts, binaries, archives, or arbitrary attachments are accepted.
- Skill versions are immutable. Activation, rollback, archive, and restore all pass through an audited change request.
- Editors may propose. Workspace admins/owners may approve. Admin/owner self-approval is allowed only through a separate explicit approval call with an audit note.
- Activation uses a row lock plus compare-and-swap against the request's expected active version. Stale requests become superseded and return HTTP 409.
- A run may load only skill versions present in its durable snapshot. If the snapshot cannot be created, skills are unavailable for that run; ordinary tools continue.
- Streaming and queued runs use the same snapshot service. HITL resumes retain the original snapshot.
- V1 limits: 32 active skills/project; description 240 characters; instructions 500 lines and approximately 5,000 tokens; at most 3 loaded skills/turn and 12,000 loaded skill tokens total.

## Phase 1: Code-first tool registry

### Task 1: Introduce registry primitives and descriptor validation

**Files:**

- Create: `backend/src/services/agent/tool_registry.py`
- Create: `backend/tests/unit/services/test_agent_tool_registry.py`

**Step 1: Write failing registry-contract tests**

Cover:

- unique descriptor names;
- one LangChain tool object per descriptor;
- valid intent/subgraph tags only;
- `destructive`, `slow`, and `no_outer_retry` policy tags;
- immutable descriptor metadata;
- deterministic ordering and a stable metadata version/hash;
- duplicate names and invalid policy combinations fail at registry construction.

The minimal public API should be explicit and typed:

```python
@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    tool: BaseTool
    intents: frozenset[AgentIntent]
    subgraphs: frozenset[AgentSubgraph]
    policy_tags: frozenset[ToolPolicyTag]
    enabled: bool = True

class ToolRegistry:
    def all_tools(self) -> tuple[BaseTool, ...]: ...
    def descriptors_for_intent(self, intent: str) -> tuple[ToolDescriptor, ...]: ...
    def descriptors_for_subgraph(self, subgraph: str) -> tuple[ToolDescriptor, ...]: ...
    def has_policy(self, name: str, tag: ToolPolicyTag) -> bool: ...
    def metadata_snapshot(self) -> dict[str, str]: ...
```

Use enums or string enums for known intents, subgraphs, and policy tags. Do not accept free-form tags.

**Step 2: Run the focused test and confirm failure**

Run: `pytest backend/tests/unit/services/test_agent_tool_registry.py -q`

Expected: import/contract failure because the registry does not exist.

**Step 3: Implement the smallest registry core**

Implement validation, lookup indexes, deterministic ordering, and SHA-256 metadata hashing. Do not register production tools yet.

**Step 4: Run the focused test**

Run: `pytest backend/tests/unit/services/test_agent_tool_registry.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/agent/tool_registry.py backend/tests/unit/services/test_agent_tool_registry.py
git commit -m "feat(agent): add tool registry primitives"
```

### Task 2: Register every existing tool and derive compatibility views

**Files:**

- Modify: `backend/src/services/agent/tools.py`
- Modify: `backend/src/services/agent/tool_registry.py`
- Modify: `backend/tests/unit/services/test_agent_tool_registry.py`
- Modify: `backend/tests/unit/services/test_agent_tools.py`
- Modify: `backend/tests/unit/services/test_agent_llm_tool_binding.py`

**Step 1: Add failing parity tests**

Capture the current contract before replacing lists:

- `ALL_TOOLS` contains exactly the same ordered names as before;
- each current intent receives exactly its prior tool names;
- each research/writing/data subgraph receives exactly its prior tool names;
- destructive names equal the current union from `_nodes_tools.py` and subgraphs;
- slow names are `ingest_arxiv_papers`, `create_draft`, `compare_documents`, and `search_arxiv`;
- no-outer-retry names are `search_arxiv` and `ingest_arxiv_papers`;
- descriptor tool objects are the existing decorated wrappers, preserving schemas and lazy `tools_impl` imports.

**Step 2: Run focused parity tests and confirm failure**

Run:

```bash
pytest backend/tests/unit/services/test_agent_tool_registry.py backend/tests/unit/services/test_agent_tools.py backend/tests/unit/services/test_agent_llm_tool_binding.py -q
```

Expected: FAIL because production descriptors and derived views are absent.

**Step 3: Define production descriptors beside the existing wrappers**

Create one descriptor per decorated tool after all wrapper definitions are available. Export a single `TOOL_REGISTRY`. Replace the hand-maintained `ALL_TOOLS` list with `list(TOOL_REGISTRY.all_tools())` so external imports remain compatible.

Do not move handler implementations or eager-import `tools_impl.py`.

**Step 4: Run focused tests**

Run the command from Step 2.

Expected: PASS with exact legacy parity.

**Step 5: Commit**

```bash
git add backend/src/services/agent/tools.py backend/src/services/agent/tool_registry.py backend/tests/unit/services/test_agent_tool_registry.py backend/tests/unit/services/test_agent_tools.py backend/tests/unit/services/test_agent_llm_tool_binding.py
git commit -m "refactor(agent): derive tools from registry descriptors"
```

### Task 3: Migrate intent, subgraph, and execution policy to descriptors

**Files:**

- Modify: `backend/src/services/agent/_nodes_llm.py`
- Modify: `backend/src/services/agent/_nodes_tools.py`
- Modify: `backend/src/services/agent/tools_impl.py`
- Modify: `backend/src/services/agent/subgraphs/research_agent.py`
- Modify: `backend/src/services/agent/subgraphs/writing_agent.py`
- Modify: `backend/src/services/agent/subgraphs/data_agent.py`
- Modify: `backend/src/services/agent/graph.py`
- Modify: `backend/tests/unit/services/test_agent_llm_tool_binding.py`
- Modify: `backend/tests/unit/agent/test_tool_timeout_tiers.py`
- Modify: `backend/tests/unit/agent/test_tool_retry_circuit_breaker.py`
- Create: `backend/tests/unit/agent/test_tool_registry_policy.py`

**Step 1: Write failing policy-consumer tests**

Prove that:

- main LLM binding asks the registry for intent tools;
- each subgraph asks the registry for its subgraph tools;
- executor authorization rejects names absent from the registry or disabled by server policy;
- confirmation, slow timeout, and outer-retry decisions query descriptor policy tags;
- the graph's `_get_execute_tool` monkeypatch seam remains effective;
- an unknown tool still returns the existing error shape;
- registry-disabled tools cannot be executed even when the model fabricates a call.

**Step 2: Run focused tests and confirm failure**

Run:

```bash
pytest backend/tests/unit/services/test_agent_llm_tool_binding.py backend/tests/unit/agent/test_tool_timeout_tiers.py backend/tests/unit/agent/test_tool_retry_circuit_breaker.py backend/tests/unit/agent/test_tool_registry_policy.py -q
```

**Step 3: Replace static sets with registry queries**

Remove `_CONTEXT_FREE_TOOLS`, `_KNOWN_TOOLS`, `_SLOW_TOOLS`, `_NO_OUTER_RETRY_TOOLS`, `DESTRUCTIVE_TOOLS`, intent-name sets, and subgraph-local tool/destructive sets only after their consumers use descriptors. Keep any compatibility export temporarily only if an existing test or import requires it, and derive it from the registry.

`make_filtered_tool_node` must enforce a registry-derived allowlist at execution time, not trust only graph construction. Tool selection remains per node/turn; do not rebuild graph topology per project.

**Step 4: Run focused and existing agent tests**

Run:

```bash
pytest backend/tests/unit/services/test_agent_tools.py backend/tests/unit/services/test_agent_llm_tool_binding.py backend/tests/unit/agent/test_tool_timeout_tiers.py backend/tests/unit/agent/test_tool_retry_circuit_breaker.py backend/tests/unit/agent/test_tool_registry_policy.py -q
```

Expected: PASS with parity tests demonstrating no policy drift.

**Step 5: Commit**

```bash
git add backend/src/services/agent backend/tests/unit/services backend/tests/unit/agent
git commit -m "refactor(agent): enforce descriptor-owned tool policies"
```

## Phase 2: Immutable project skill catalog

### Task 4: Add PostgreSQL skill and runtime snapshot models

**Files:**

- Create: `backend/src/models/project_skill.py`
- Create: `backend/src/models/agent_runtime_snapshot.py`
- Modify: `backend/src/models/__init__.py`
- Create: `backend/alembic/versions/<revision>_add_project_skills_and_runtime_snapshots.py`
- Create: `backend/tests/unit/models/test_project_skill_models.py`

**Step 1: Write failing model/constraint tests**

Cover model metadata for:

- `project_skills`: project ID, normalized unique name per project, active version ID, archived state, creator;
- `project_skill_versions`: skill ID, monotonically increasing version, canonical instructions, parsed name/description, content hash, scan state/findings/scanner version, author;
- `project_skill_change_requests`: action, proposed/prior version, expected active version, requester, reviewer, status, warning acknowledgement, audit note, timestamps;
- `agent_runtime_snapshots`: project/user/thread/job links where available, tool registry hash/version, frozen tool metadata JSON, frozen skill catalog JSON, loaded skill versions JSON, created/expiry timestamps.

Add database constraints for normalized-name uniqueness, skill/version uniqueness, valid status/action values, and foreign keys. Avoid hard deletes for audited rows.

**Step 2: Run model test and confirm failure**

Run: `pytest backend/tests/unit/models/test_project_skill_models.py -q`

**Step 3: Implement models and migration**

Generate a new Alembic revision whose `down_revision` is `b8s2a4t7e0l3`. Use PostgreSQL JSONB consistently with existing models. Resolve the circular active-version foreign key explicitly with named constraints and relationship `foreign_keys` declarations.

**Step 4: Validate upgrade/downgrade SQL and focused tests**

Run:

```bash
pytest backend/tests/unit/models/test_project_skill_models.py -q
alembic -c backend/alembic.ini upgrade head --sql > /tmp/project-skills-upgrade.sql
```

Inspect SQL for all indexes/constraints and a reversible downgrade. Do not apply against an unverified shared database.

**Step 5: Commit**

```bash
git add backend/src/models backend/alembic/versions backend/tests/unit/models/test_project_skill_models.py
git commit -m "feat(skills): add immutable catalog and runtime snapshot models"
```

### Task 5: Implement canonical SKILL.md parsing and scanning

**Files:**

- Create: `backend/src/services/project_skills/skill_document.py`
- Create: `backend/src/services/project_skills/scanner.py`
- Create: `backend/src/services/project_skills/__init__.py`
- Create: `backend/tests/unit/services/project_skills/test_skill_document.py`
- Create: `backend/tests/unit/services/project_skills/test_scanner.py`

**Step 1: Write failing parser/scanner tests**

Test canonical YAML frontmatter plus Markdown instructions, normalized lowercase kebab-case names, deterministic serialization/content hashing, and line/token estimates.

Scanner blocking findings:

- malformed/missing metadata;
- invalid or duplicate normalized name;
- description over 240 characters;
- instructions over 500 lines or estimated 5,000 tokens;
- embedded secrets/private keys/tokens;
- executable, archive, attachment, or unsupported payload markers.

Scanner warning findings:

- unknown tool references checked against `TOOL_REGISTRY`;
- external-network instructions;
- destructive-action language;
- attempts to bypass approval or policy.

Results must be stable structured codes with severity, message, and line where possible; scanner errors block activation until a successful rescan.

**Step 2: Run focused tests and confirm failure**

Run:

```bash
pytest backend/tests/unit/services/project_skills/test_skill_document.py backend/tests/unit/services/project_skills/test_scanner.py -q
```

**Step 3: Implement deterministic parser and scanner**

Keep scanning synchronous and pure. Do not execute, import, fetch, or render skill content. Token estimates may use a documented deterministic approximation to avoid adding a runtime tokenizer dependency.

**Step 4: Run focused tests**

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/project_skills backend/tests/unit/services/project_skills
git commit -m "feat(skills): parse and scan instruction documents"
```

### Task 6: Implement catalog, proposal, and atomic approval service

**Files:**

- Create: `backend/src/services/project_skills/access.py`
- Create: `backend/src/services/project_skills/catalog_service.py`
- Create: `backend/src/services/project_skills/approval_service.py`
- Create: `backend/tests/unit/services/project_skills/test_catalog_service.py`
- Create: `backend/tests/unit/services/project_skills/test_approval_service.py`
- Create: `backend/tests/integration/test_project_skill_approval.py`

**Step 1: Write failing authorization and transaction tests**

Cover:

- viewer can list/read only;
- editor can create a draft identity and propose a version/change;
- admin/owner can approve/reject/rescan;
- ordinary editor cannot approve;
- admin/owner self-approval requires an explicit `self_approval_acknowledged` value and non-empty note;
- blockers reject approval; warnings require acknowledgement plus note;
- immutable version rows cannot be mutated by service methods;
- max 32 active skills/project;
- row lock plus expected-active-version CAS;
- two concurrent approvals produce one activation and one superseded HTTP-conflict result;
- rollback creates a change request targeting a prior approved version rather than editing history;
- archive/restore are staged and audited.

Use `Collection.workspace_id` and `Workspace.can_user_edit`/`can_user_admin`; do not substitute organization membership.

**Step 2: Run focused tests and confirm failure**

Run:

```bash
pytest backend/tests/unit/services/project_skills/test_catalog_service.py backend/tests/unit/services/project_skills/test_approval_service.py backend/tests/integration/test_project_skill_approval.py -q
```

**Step 3: Implement service transactions**

Services receive an `AsyncSession`, explicit project/user IDs, and no HTTP types. Approval must lock the `project_skills` identity row, compare the active version with the request's expected version, write reviewer/audit fields, update the active pointer, and commit atomically. Return typed domain errors for API translation.

**Step 4: Run focused tests**

Expected: PASS, including the concurrent approval test on PostgreSQL. If SQLite is used by unit tests, keep the concurrency assertion in the PostgreSQL integration suite rather than weakening it.

**Step 5: Commit**

```bash
git add backend/src/services/project_skills backend/tests/unit/services/project_skills backend/tests/integration/test_project_skill_approval.py
git commit -m "feat(skills): add staged atomic approval workflow"
```

### Task 7: Expose the project skill API and OpenAPI contract

**Files:**

- Create: `backend/src/schemas/project_skills.py`
- Create: `backend/src/api/research/project_skills.py`
- Modify: `backend/src/api/research/__init__.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/unit/api/test_project_skills_api.py`
- Create: `backend/tests/integration/test_project_skills_api.py`
- Modify generated OpenAPI artifacts only through the repository generator.

**Step 1: Write failing endpoint tests**

Implement and test endpoints below `/api/v1/projects/{project_id}/skills`:

- `GET /` list active/pending/history summaries according to role;
- `POST /` create identity plus first proposed immutable version;
- `GET /{skill_name}` detail and version history;
- `POST /{skill_name}/versions` propose a new version;
- `GET /{skill_name}/diff?from_version=&to_version=` canonical unified diff;
- `POST /change-requests/{request_id}/approve`;
- `POST /change-requests/{request_id}/reject`;
- `POST /change-requests/{request_id}/rescan`;
- `POST /{skill_name}/archive` and `/restore` to create staged requests;
- `POST /{skill_name}/rollback` to propose reactivation of an earlier version.

Assert 401/403/404 without leaking cross-project existence, 409 for stale activation, and 422 for malformed documents/acknowledgements.

**Step 2: Run endpoint tests and confirm failure**

Run:

```bash
pytest backend/tests/unit/api/test_project_skills_api.py backend/tests/integration/test_project_skills_api.py -q
```

**Step 3: Implement schemas and thin router**

Router performs authentication, delegates to project-skill services, and translates typed domain errors. Keep transactions in services. Include the router exactly once and confirm the final prefix in `main.py` to avoid doubled `/api/v1` paths.

**Step 4: Verify API and OpenAPI**

Run:

```bash
pytest backend/tests/unit/api/test_project_skills_api.py backend/tests/integration/test_project_skills_api.py -q
python scripts/ci/generate_openapi.py
python scripts/ci/generate_openapi.py --check
```

**Step 5: Commit**

```bash
git add backend/src/api/research backend/src/schemas/project_skills.py backend/src/main.py backend/tests/unit/api/test_project_skills_api.py backend/tests/integration/test_project_skills_api.py frontend/src/types/generated
git commit -m "feat(skills): expose project catalog approval API"
```

## Phase 3: Runtime snapshot and progressive loading

### Task 8: Build the transport-neutral runtime snapshot service

**Files:**

- Create: `backend/src/services/agent/runtime_snapshot.py`
- Modify: `backend/src/core/config.py`
- Create: `backend/tests/unit/services/test_agent_runtime_snapshot.py`

**Step 1: Write failing snapshot tests**

Test:

- snapshot contains the registry metadata hash/version and exact enabled descriptor names;
- verified project turns include only approved active, non-archived skill versions;
- absent/unverified project context produces an empty skill catalog;
- snapshot rows are committed before graph execution;
- failed snapshot persistence yields an ordinary-tools-only result and never an in-memory skill catalog;
- catalog is capped at 32 entries and only name/description/version/hash are injected;
- tool and skill versions cannot change within a snapshot after activation changes elsewhere;
- expiry/retention is explicit and does not delete snapshots needed by active HITL/queued work.

Add settings, defaulting safely for staged rollout:

```python
AGENT_TOOL_REGISTRY_ENFORCEMENT_ENABLED: bool = False
PROJECT_SKILL_CATALOG_ENABLED: bool = False
PROJECT_SKILL_RUNTIME_ENABLED: bool = False
PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS: int = 30
```

Registry parity/shadow logging may run with enforcement disabled.

**Step 2: Run focused test and confirm failure**

Run: `pytest backend/tests/unit/services/test_agent_runtime_snapshot.py -q`

**Step 3: Implement snapshot creation and lookup**

The service validates project access using the authenticated user, freezes descriptor and skill metadata, commits the row, and returns a compact immutable DTO. Link queued `job_id` where available, but do not repurpose `AgentRun` or broaden its sweeper semantics.

**Step 4: Run focused tests**

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/agent/runtime_snapshot.py backend/src/core/config.py backend/tests/unit/services/test_agent_runtime_snapshot.py
git commit -m "feat(agent): snapshot tool and skill versions per run"
```

### Task 9: Add the read-only `load_project_skill` tool

**Files:**

- Modify: `backend/src/services/agent/tools.py`
- Modify: `backend/src/services/agent/tools_impl.py`
- Modify: `backend/src/services/agent/tool_registry.py`
- Create: `backend/tests/unit/services/test_load_project_skill_tool.py`

**Step 1: Write failing tool tests**

Test that the tool:

- is read-only, non-destructive, context-required, and available only when project skill runtime is enabled;
- accepts a normalized skill name only;
- requires `runtime_snapshot_id` from server execution context, never model arguments;
- loads the exact version/hash frozen in the snapshot even after a newer activation;
- rejects names absent from the snapshot, cross-project access, expired/unavailable snapshots, and a fourth unique load;
- enforces the 12,000-token per-turn aggregate;
- returns canonical instructions plus name/version/hash and structured errors;
- records loaded versions in run state/snapshot audit data without mutating the skill version.

**Step 2: Run focused test and confirm failure**

Run: `pytest backend/tests/unit/services/test_load_project_skill_tool.py -q`

**Step 3: Implement through the existing lazy dispatcher**

Add the decorated wrapper and descriptor, but resolve snapshot/project/user context server-side in `tools_impl`. Never expose `runtime_snapshot_id`, user ID, or project ID as model-controlled schema fields. Keep the exact `_get_execute_tool` patch seam used by graph tests.

**Step 4: Run focused and registry tests**

Run:

```bash
pytest backend/tests/unit/services/test_load_project_skill_tool.py backend/tests/unit/services/test_agent_tool_registry.py backend/tests/unit/services/test_agent_tools.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/agent backend/tests/unit/services/test_load_project_skill_tool.py
git commit -m "feat(agent): progressively load frozen project skills"
```

### Task 10: Inject snapshots into streaming, queued, main, and subgraph execution

**Files:**

- Modify: `backend/src/services/agent/state.py`
- Modify: `backend/src/api/agent/streaming.py`
- Modify: `backend/src/services/agent/agent_execution_service.py`
- Modify: `backend/src/services/agent/_nodes_llm.py`
- Modify: `backend/src/services/agent/_nodes_tools.py`
- Modify: `backend/src/services/agent/subgraphs/research_agent.py`
- Modify: `backend/src/services/agent/subgraphs/writing_agent.py`
- Modify: `backend/src/services/agent/subgraphs/data_agent.py`
- Modify: `backend/src/services/agent/graph.py`
- Modify: `backend/tests/unit/api/test_agent_project_binding.py`
- Modify: `backend/tests/unit/api/test_agent_streaming_done_tool_executions.py`
- Create: `backend/tests/unit/agent/test_project_skill_runtime.py`

**Step 1: Write failing end-to-end runtime tests**

Cover both transports:

- authenticated project binding creates a durable snapshot before execution;
- initial `AgentState` contains `runtime_snapshot_id`, compact `project_skill_catalog`, and `loaded_skill_versions`;
- system prompt shows a concise catalog and instructions to call `load_project_skill(name)` only when relevant;
- unverified/no-project turns receive no skill catalog and cannot load skills;
- main and subgraph LLM bindings include the loader only when the snapshot has skills and runtime flag is enabled;
- newly approved versions do not alter an in-flight turn;
- queued execution links the job to the same snapshot;
- HITL resume preserves the original snapshot ID and limits;
- snapshot failure continues with ordinary registry tools and an empty catalog;
- streaming done events and tool-execution audit output remain backward compatible.

**Step 2: Run runtime tests and confirm failure**

Run:

```bash
pytest backend/tests/unit/agent/test_project_skill_runtime.py backend/tests/unit/api/test_agent_project_binding.py backend/tests/unit/api/test_agent_streaming_done_tool_executions.py -q
```

**Step 3: Wire the snapshot into both initial-state constructors**

Add all new `AgentState` fields to every constructor and resume path. Prompt construction must use only frozen catalog metadata from state; tool loading uses the snapshot row. Keep prompt catalog formatting deterministic and bounded. Do not query live active skill pointers after the snapshot exists.

**Step 4: Run focused agent suite**

Run:

```bash
pytest backend/tests/unit/agent/test_project_skill_runtime.py backend/tests/unit/api/test_agent_project_binding.py backend/tests/unit/api/test_agent_streaming_done_tool_executions.py backend/tests/unit/services/test_agent_llm_tool_binding.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/agent backend/src/api/agent/streaming.py backend/tests/unit/agent/test_project_skill_runtime.py backend/tests/unit/api
git commit -m "feat(agent): inject frozen project skills into every run"
```

## Phase 4: Project Skills UI

### Task 11: Add the typed frontend API adapter and TanStack Query hooks

**Files:**

- Create: `frontend/src/services/projectSkillService.ts`
- Create: `frontend/src/hooks/useProjectSkills.ts`
- Create: `frontend/src/services/__tests__/projectSkillService.test.ts`
- Create: `frontend/src/hooks/__tests__/useProjectSkills.test.tsx`
- Modify generated types only via `python scripts/ci/generate_openapi.py`.

**Step 1: Write failing adapter/hook tests**

Cover list/detail/history/diff/create/propose/approve/reject/rescan/archive/restore/rollback. Verify TanStack Query keys include `projectId`, detail/version identifiers, and pending filters. Mutations must invalidate list, detail, pending, diff, and history keys as appropriate.

Use generated OpenAPI request/response types. Do not add skill server state to `projectStore`.

**Step 2: Run focused tests and confirm failure**

Run:

```bash
corepack pnpm@10.18.2 --dir frontend test -- --run src/services/__tests__/projectSkillService.test.ts src/hooks/__tests__/useProjectSkills.test.tsx
```

**Step 3: Implement adapter and hooks**

Follow the existing authenticated API client conventions in `projectService.ts`, but keep this domain in a separate focused module.

**Step 4: Run focused tests and type-check**

Run:

```bash
corepack pnpm@10.18.2 --dir frontend test -- --run src/services/__tests__/projectSkillService.test.ts src/hooks/__tests__/useProjectSkills.test.tsx
corepack pnpm@10.18.2 --dir frontend type-check
```

**Step 5: Commit**

```bash
git add frontend/src/services/projectSkillService.ts frontend/src/hooks/useProjectSkills.ts frontend/src/services/__tests__/projectSkillService.test.ts frontend/src/hooks/__tests__/useProjectSkills.test.tsx frontend/src/types/generated
git commit -m "feat(frontend): add project skill catalog client"
```

### Task 12: Build the project Skills tab and approval experience

**Files:**

- Create: `frontend/src/components/research/ProjectSkillsTab.tsx`
- Create: `frontend/src/components/research/project-skills/SkillList.tsx`
- Create: `frontend/src/components/research/project-skills/SkillEditor.tsx`
- Create: `frontend/src/components/research/project-skills/SkillReviewPanel.tsx`
- Create: `frontend/src/components/research/project-skills/SkillHistory.tsx`
- Create: `frontend/src/components/research/project-skills/__tests__/ProjectSkillsTab.test.tsx`
- Modify: `frontend/app/(dashboard)/projects/[id]/page.tsx`
- Modify: the local `TabType` declaration in the same page or its existing source.

**Step 1: Write failing UI behavior tests**

Test:

- Skills appears as a secondary project-detail tab when the backend capability is enabled;
- active skill list shows name, description, active version, scan status, pending status, and archived state;
- editor can create/propose but does not see approval controls;
- admin/owner review shows canonical diff and structured blocker/warning findings;
- blocker disables approval;
- warning approval requires acknowledgement and note;
- self-approval requires the explicit acknowledgement and note;
- stale 409 refreshes data and explains supersession;
- history can stage rollback, never directly mutate active state;
- loading, empty, error, keyboard, focus, and accessible-label states work.

Mock the service boundary, not global `fetch` deep inside component tests.

**Step 2: Run focused test and confirm failure**

Run:

```bash
corepack pnpm@10.18.2 --dir frontend test -- --run src/components/research/project-skills/__tests__/ProjectSkillsTab.test.tsx
```

**Step 3: Implement focused components**

Keep `projects/[id]/page.tsx` as the composition root: add the tab descriptor and render `<ProjectSkillsTab projectId={projectId} />`; keep editor/review/history state inside the new domain components. Reuse existing buttons, dialogs, badges, text areas, and diff styling before adding primitives.

Do not rely solely on the mock LaunchDarkly service. Derive visibility from an authenticated backend catalog/capability response, while treating 404/disabled as unavailable.

**Step 4: Run focused tests and frontend gates**

Run:

```bash
corepack pnpm@10.18.2 --dir frontend test -- --run src/components/research/project-skills/__tests__/ProjectSkillsTab.test.tsx src/components/research/__tests__/ProjectDetailPage.agent-sync.test.tsx
corepack pnpm@10.18.2 --dir frontend type-check
corepack pnpm@10.18.2 --dir frontend lint:changed
corepack pnpm@10.18.2 --dir frontend quality:exclusions
```

**Step 5: Commit**

```bash
git add frontend/src/components/research frontend/app/'(dashboard)'/projects/'[id]'/page.tsx
git commit -m "feat(frontend): add project skill approval workspace"
```

## Phase 5: Rollout, observability, and final verification

### Task 13: Add metrics, audit logs, parity shadowing, and operator documentation

**Files:**

- Modify: `backend/src/services/agent/tool_registry.py`
- Modify: `backend/src/services/agent/runtime_snapshot.py`
- Modify: `backend/src/services/project_skills/approval_service.py`
- Create: `docs/operations/project-skills-rollout.md`
- Modify: relevant environment example/Helm values files discovered with `rg` before editing.
- Create or modify focused observability tests under `backend/tests/unit/services/`.

**Step 1: Write failing observability tests**

Assert structured events/metrics for registry parity mismatch, snapshot creation/failure, scan result, proposal, approval/rejection/supersession, loader success/rejection, loaded-skill count/tokens, and stale request conflicts. Never log skill instructions or secrets.

**Step 2: Run focused test and confirm failure**

Use the exact focused test path selected in Step 1.

**Step 3: Implement safe telemetry and rollout docs**

Document this staged sequence:

1. deploy registry in parity/shadow mode;
2. alert on parity mismatch;
3. enable registry enforcement;
4. enable catalog API/UI for dev workspaces;
5. enable runtime progressive loading in dev;
6. validate snapshots/HITL/queued behavior;
7. enable production cohorts;
8. remove any remaining derived legacy compatibility exports only after callers are gone.

Include rollback behavior for each flag and snapshot-retention operations.

**Step 4: Run focused tests**

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/agent backend/src/services/project_skills backend/tests docs/operations
git commit -m "docs(agent): add safe project skills rollout controls"
```

### Task 14: Run full changed-file gates and perform adversarial review

**Files:** all files changed by Tasks 1-13.

**Step 1: Backend format/lint**

Run the repository-pinned changed-Python gate if available. At minimum:

```bash
ruff check backend/src backend/tests
black --check backend/src backend/tests
isort --check-only backend/src backend/tests
```

Use the versions pinned by CI; do not silently substitute globally installed versions.

**Step 2: Backend tests and OpenAPI drift**

Run:

```bash
pytest backend/tests/unit/services/test_agent_tool_registry.py backend/tests/unit/services/project_skills backend/tests/unit/agent/test_project_skill_runtime.py backend/tests/unit/api/test_project_skills_api.py backend/tests/integration/test_project_skill_approval.py backend/tests/integration/test_project_skills_api.py -q
python scripts/ci/generate_openapi.py --check
```

Then run the broader agent/project suites if time permits:

```bash
pytest backend/tests/unit/agent backend/tests/unit/services/test_agent_tools.py backend/tests/unit/services/test_agent_llm_tool_binding.py backend/tests/unit/api/test_agent_project_binding.py backend/tests/integration/test_projects_api.py -q
```

**Step 3: Frontend gates**

Run:

```bash
corepack pnpm@10.18.2 --dir frontend test -- --run src/services/__tests__/projectSkillService.test.ts src/hooks/__tests__/useProjectSkills.test.tsx src/components/research/project-skills/__tests__/ProjectSkillsTab.test.tsx src/components/research/__tests__/ProjectDetailPage.agent-sync.test.tsx
corepack pnpm@10.18.2 --dir frontend type-check
corepack pnpm@10.18.2 --dir frontend lint:changed
corepack pnpm@10.18.2 --dir frontend quality:exclusions
```

**Step 4: Adversarial review checklist**

Verify from code and tests:

- no static intent/destructive/context-free/timeout/retry name sets remain;
- no database value can choose a handler/import path;
- project authorization always follows workspace membership;
- versions and audit records are immutable;
- self-approval is separately explicit and audited;
- approval CAS cannot silently overwrite a newer activation;
- scanner findings cannot be bypassed by alternate endpoints;
- prompt contains no unapproved or live-mutating skill content;
- model arguments cannot select snapshot/project/user context;
- tool execution reauthorizes at the registry boundary;
- both transports and HITL use the frozen snapshot;
- feature-flag-off behavior matches the current product.

**Step 5: Commit only verification-driven corrections**

```bash
git add <specific-corrected-files>
git commit -m "fix(agent): harden project skill registry rollout"
```

Skip this commit if review produces no changes.

## Definition of done

- Every production tool has one validated descriptor and `ALL_TOOLS` is derived.
- All policy decisions are descriptor/server-policy driven with parity coverage.
- Project skills support immutable history, scanning, proposals, diffs, approval/rejection, archive/restore, and rollback.
- Role enforcement and stale-approval CAS are integration-tested against PostgreSQL.
- Streaming, queued, and HITL paths freeze tool/skill versions in a durable snapshot.
- Approved project skills are progressively loaded under strict per-turn limits.
- The project detail Skills tab supports editor proposals and admin/owner review without expanding the legacy page's state responsibilities.
- Feature flags permit independent rollback of registry enforcement, catalog, and runtime loading.
- Focused backend/frontend suites, formatting, type-check, changed-file gates, and OpenAPI drift checks pass, or each environment-only blocker is reported with exact command/output.
