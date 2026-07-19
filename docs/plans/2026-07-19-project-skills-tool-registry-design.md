# Project Skills and Dynamic Tool Registry Design

**Date:** 2026-07-19
**Status:** Approved
**Target:** Existing NOUS FastAPI/Next.js product

## Summary

NOUS will replace its duplicated static tool-name policy with a code-first
registry and add a PostgreSQL-backed, project-scoped skill catalog. Project
editors can propose instruction-only skills; workspace admins and owners review
and atomically activate immutable versions. Project agent turns receive a small
catalog and progressively load only relevant approved instructions.

The compiled LangGraph topology remains unchanged. Tool and skill resolution
happens dynamically inside existing nodes so current execution, HITL, timeout,
retry, checkpoint, and test patch seams remain compatible.

## Decisions

- Trusted tool handlers and canonical schemas remain in Python. PostgreSQL
  never stores importable handler paths.
- `ALL_TOOLS` remains public as a registry-derived compatibility view.
- Descriptor policy replaces intent, destructive, context-free, timeout, and
  retry name sets.
- Policy is checked before tool binding and immediately before execution.
- Skills are scoped to research projects (`collections`) and inherit workspace
  access and roles.
- Editors, admins, and owners may propose. Admins and owners approve or reject.
  An admin or owner may approve their own proposal, but the separate approval
  action is durably audited.
- V1 authoring is human-only and instructions-only. Scripts, assets, remote
  imports, marketplace installs, and agent-authored proposals are out of scope.
- Skills use progressive disclosure: compact metadata is always available in a
  project turn; full instructions load only through an internal read-only tool.
- The Skills UI lives in a secondary tab on the project detail page.

## Tool Registry Architecture

A dependency-light registry owns frozen tool descriptors. Each descriptor
contains:

- stable key and descriptor version;
- LangChain tool/schema object and schema hash;
- intent and capability tags;
- effect classification and independent approval policy;
- execution-session profile;
- timeout and outer-retry policy;
- availability check and observability metadata.

Tool modules register LangChain schemas, and the implementation module binds
trusted executor adapters. Registry validation runs at application startup and
fails on duplicate names, missing executors, invalid metadata, or schema drift.

`ALL_TOOLS` becomes `registry.all_langchain_tools()`. Main and subgraph LLM
nodes resolve tools by intent tags. Destructive routing reads approval policy;
the dispatcher uses the bound executor and execution-session profile instead
of `_KNOWN_TOOLS`, `_CONTEXT_FREE_TOOLS`, and an `if` chain.

A server-owned resolver intersects descriptor eligibility, project policy,
runtime availability, and caller access. The selected tools are bound to the
model. The executor repeats the same authorization before invocation to close
the time-of-check/time-of-use gap.

## Skill Catalog and Approval Model

### Persistence

`project_skills` stores the stable project-scoped identity, normalized name,
active-version pointer, archived state, creator, and timestamps. Names are
unique within a project.

`project_skill_versions` stores immutable monotonically numbered versions:
canonical `SKILL.md`, parsed name and description, content hash, scan result,
scanner version, author, and creation time.

`project_skill_change_requests` is an append-only workflow record containing
the action, proposed version, expected active version, requester, reviewer,
status, decision note, and decision timestamps. It supports create, update,
archive, restore, and rollback-as-reactivation without hard deletion.

### Approval transaction

Approval locks the skill row and verifies that its active version still equals
the request's expected base. In one transaction it records the decision and
switches the active-version pointer. If the base changed, the request becomes
`superseded` and the API returns HTTP 409. Rejection never changes the active
version.

Versions are never edited in place. Rollback creates a new staged activation
request pointing at a previously approved version. Archive follows the same
approval path.

### Validation and scanning

The backend constructs canonical instruction-only `SKILL.md` content from a
name, description, and Markdown instructions. The deterministic scanner:

- blocks malformed Agent Skills metadata, invalid names, excessive content,
  embedded secrets, and unsupported executable or file payloads;
- warns on unknown tool references, external instructions, destructive
  language, or attempts to bypass approval;
- snapshots findings and scanner version with the immutable version.

Blocked versions cannot be approved. Warning-bearing versions require an
explicit acknowledgement and reviewer decision note. Scanner errors fail
closed until a rescan succeeds.

## API and UI

Project-scoped routes under `/api/v1/projects/{project_id}/skills` provide:

- catalog and pending-review listing;
- create and update proposals;
- detail, immutable version history, hashes, and scan findings;
- server-generated unified diffs;
- approve, reject, rescan, archive, restore, and rollback proposal actions.

All handlers use the existing project/workspace access funnel. Responses expose
effective `can_edit` and `can_approve` flags. Editors and above may propose;
admins and owners may decide.

The project page gains a focused `Skills` secondary tab. It shows active
skills, structured authoring, version history, pending reviews, server-generated
diffs, scan findings, and role-appropriate actions. TanStack Query owns this
server state; `projectStore` is not extended. The frontend service consumes
generated OpenAPI types through a domain adapter.

## Runtime Integration

Before each project-bound graph invocation, both SSE and queued transports load
the approved active catalog and create a transport-neutral runtime snapshot.
The snapshot ID is stored in LangGraph state and configurable metadata so it
survives HITL pause and resume.

The dynamic prompt receives only skill name, description, and version. The
internal read-only `load_project_skill(name)` tool resolves the exact version
captured at turn start, rechecks access, returns the canonical instructions,
and records the loaded version and hash. An approval during a running turn
cannot change that turn's instructions.

The runtime snapshot records:

- registry revision;
- eligible tool descriptor versions and schema hashes;
- active project skill versions at turn start;
- skill versions actually loaded during the turn;
- user, organization, project, thread, transport, and job correlation IDs.

The existing Redis-oriented `AgentRun` lifecycle is unchanged. Queued runs link
to the runtime snapshot; streaming turns use the same snapshot store without
entering the lost-job or sweeper lifecycle.

### V1 limits

- At most 32 active skills per project.
- Descriptions are capped at 240 characters.
- Instructions are capped at 500 lines and approximately 5,000 tokens.
- A turn may load at most three skills and 12,000 total skill tokens.
- Project skills are unavailable when no verified project binding exists.

## Failure Handling and Observability

- Invalid core registry configuration fails application startup.
- Availability-check failure omits the affected tool for the turn.
- Policy denial returns a structured tool error and audit event.
- Catalog or runtime-snapshot failure degrades the turn to no project skills;
  ordinary tools continue. A skill never loads without a durable snapshot.
- Audit and trace records contain IDs, versions, hashes, finding codes, and
  decisions, never skill bodies.
- Metrics cover registry resolution, parity differences, policy denials, skill
  scans, proposals, approvals, loads, load denials, and degraded turns.

## Rollout

1. Add descriptors and assert registry-derived sets match legacy behavior in
   tests and shadow logging.
2. Switch tool binding, approval routing, session selection, timeout, retry,
   and dispatch to registry policy behind a backend flag.
3. Enable the catalog API and project Skills tab behind a separate flag.
4. Enable runtime skill loading in development, then production, while
   observing load, denial, error, latency, and token metrics.
5. Remove legacy policy sets and dispatch chains after parity and production
   observation; retain only the derived `ALL_TOOLS` compatibility export.

## Testing and Acceptance

- Registry validation proves unique descriptors, bound executors, stable schema
  hashes, exact legacy parity, and derived `ALL_TOOLS` compatibility.
- Policy tests pin every current tool's intent, approval, session, timeout, and
  retry behavior and verify pre-bind plus pre-execution authorization.
- Service and API tests cover tenant access, role enforcement, immutable
  versions, scans, warning acknowledgement, stale approval races, atomic
  activation, archive/restore, and rollback proposals.
- Runtime tests prove only approved project skills are visible, the exact
  frozen version loads after concurrent activation, limits are enforced, and
  HITL resume retains the same snapshot.
- Both SSE and queued execution paths create and seal snapshots while feature
  flags off preserve current behavior.
- Frontend tests cover authoring, diff and scan presentation, permission-aware
  actions, pending-review states, keyboard navigation, and accessibility.
- OpenAPI generation, focused backend suites, changed-file quality gates,
  frontend type-check, and focused frontend tests pass.
