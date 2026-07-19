# Project skills rollout

Project skills are an instructions-only, project-scoped catalog. The backend
freezes the enabled tool metadata and the approved catalog before a run starts;
the model can load only a named version in that durable snapshot.

## Controls

All controls are backend environment variables and default to false except
retention.

| Variable | Effect | Immediate rollback |
| --- | --- | --- |
| AGENT_TOOL_REGISTRY_ENFORCEMENT_ENABLED | Persists/enforces the code-owned registry snapshot; supports parity shadowing before enforcement. | Set false; normal tools remain available. |
| PROJECT_SKILL_CATALOG_ENABLED | Makes the project catalog capability/API available. Disabled responses are a non-leaking 404/feature-unavailable result so the frontend probe hides the Skills tab. | Set false; no catalog is exposed. |
| PROJECT_SKILL_RUNTIME_ENABLED | Enables progressive load_project_skill for a run with a durable non-empty catalog. | Set false; existing snapshots may be retained, but loaders reject new calls. |
| PROJECT_SKILL_SNAPSHOT_RETENTION_DAYS | Retains durable runtime snapshots for audit and HITL/queued resume. | Increase during investigation; do not set below active run lifetime. |

The GitOps dev overlay is infrastructure/helm/knowledge-graph-analytics/values-dev.yaml.
It explicitly sets enforcement, catalog, and runtime to true, with 30-day
retention. Production defaults stay off in values-production.yaml; do not
promote the dev values wholesale.

## Staged rollout

1. Deploy descriptor registry with enforcement off and inspect parity-shadow
   events.
2. Alert on any registry-parity mismatch.
3. Enable registry enforcement in dev.
4. Enable catalog API/UI in selected dev workspaces; confirm a disabled
   capability hides the frontend tab rather than showing an authorization
   error.
5. Enable runtime progressive loading in dev.
6. Validate a streaming run, queued run, and HITL resume use the same snapshot
   and only expose the loader for a non-empty durable catalog.
7. Promote explicit production cohorts only after the dev soak has no parity,
   snapshot-failure, or loader-rejection regression.
8. Remove derived legacy compatibility exports only after callers are gone.

Operational telemetry is intentionally low-cardinality:
project_skill_events_total records registry parity, snapshot outcomes,
scan/proposal/approval/rejection/supersession/rescan, and loader outcomes.
project_skill_loaded_skills_total and project_skill_loaded_tokens_total record
successful new loads. Logs and metrics must never include instructions, audit
notes, scanner finding text, secrets, project IDs, user IDs, or skill names.

## Rollback and retention

Disable runtime first to stop further instruction loads; disable catalog next
to remove the API/UI capability; disable enforcement last only if the registry
migration itself must be rolled back. These are values-only changes and do not
delete skill history or snapshots.

Snapshots are audit records and preserve queued and HITL reproducibility.
Before shortening retention or deleting expired rows, verify no queued job,
active checkpoint, or pending HITL resume refers to them. Retain snapshots
longer during incident analysis. Skill versions, scan rows, and approval
records are append-only and are not deleted as a normal rollback action.

## Database migration

Project skills require the PostgreSQL migration containing the JSONB snapshot
columns and immutable catalog constraints. The dev Helm overlay has
backend.initContainers.runMigrations: true, which runs alembic upgrade heads
against the deployed PostgreSQL database before the app starts.

Do not treat alembic upgrade head --sql as a successful migration: offline
Alembic only emits PostgreSQL SQL and cannot apply it, inspect the live schema,
or validate the migration against SQLite. Review the generated SQL, then run
the migration against the intended PostgreSQL database through the approved
deployment/change process. Production keeps automatic migrations disabled and
requires its own backup and explicit migration step.
