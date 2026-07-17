# API contracts

FastAPI/Pydantic is the HTTP source of truth. Nothing downstream is
hand-typed against a guess of the wire shape — it's generated from the app
itself.

## Pipeline

1. `python scripts/ci/generate_openapi.py` rebuilds `backend/openapi.json`
   by constructing the FastAPI app in-memory (SQLite, placeholder Azure
   creds — no DB/Redis/network) and calling `app.openapi()`.
2. `pnpm --dir frontend generate:api-types` (openapi-typescript) rebuilds
   `frontend/src/types/generated/api.d.ts` from that committed snapshot.
3. CI's `openapi-contract` job blocks on **both** halves drifting:
   `python scripts/ci/generate_openapi.py --check` (backend schema vs. the
   running app), then it regenerates the TypeScript and runs
   `git diff --exit-code -- backend/openapi.json
   frontend/src/types/generated/api.d.ts`. A schema change and its
   regenerated types must land in the same PR — commit both together.

## Adopt-on-touch

- Alias generated shapes from `components['schemas'][...]`; don't re-type
  them by hand. `frontend/src/types/api/workspace-contract.ts` is the
  worked example for the workspace resource hierarchy.
- Migration is **per-file, on touch** — editing a hand-written type that
  owns an HTTP request/response shape is the trigger to alias it from the
  generated schema, not a mandate to migrate every type at once.
  `frontend/src/types/README.md` lists current adopters
  (`services/documentAnalyticsApi.ts`, `services/workspaceService.ts`).
- Where a generated field is looser than the frontend needs (a JSONB
  passthrough column typed `Record<string, unknown>[]`) or stricter than
  the wire contract actually requires (`openapi-typescript`'s
  `defaultNonNullable` marks any Pydantic-defaulted field as required, even
  though a caller may still omit it), narrow or relax it with an explicit
  derived type in the adopting module. Never paper over a mismatch with
  `as unknown as` — that's exactly the drift this pipeline exists to catch.
- Frontend-only concepts (streaming frames, planner steps, optimistic ids,
  UI enums, view models) stay hand-written; only wire request/response
  shapes are candidates for aliasing.

## Commands

```sh
python scripts/ci/generate_openapi.py            # refresh backend/openapi.json
python scripts/ci/generate_openapi.py --check     # verify no drift
pnpm --dir frontend generate:api-types            # rebuild generated/api.d.ts
pnpm --dir frontend check:api-types               # regenerate + diff both in one step
git diff --exit-code -- backend/openapi.json frontend/src/types/generated/api.d.ts
```
