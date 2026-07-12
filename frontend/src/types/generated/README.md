# `src/types/generated/` — auto-generated API types

**Do not hand-edit anything in this directory.** `api.d.ts` is generated from
the backend's OpenAPI schema and is overwritten on every regeneration.

This is the frontend half of the **REST contract ratchet** (audit finding C5).
The FastAPI app is the single source of truth for the REST contract; these
types are derived from it so the frontend can never silently drift from the
backend response models the way the hand-mirrored types in `../` did.

## The loop

```
backend Pydantic model changes
        │
        ▼
python scripts/ci/generate_openapi.py      # rebuild backend/openapi.json
        │
        ▼
cd frontend && pnpm generate:api-types     # rebuild src/types/generated/api.d.ts
        │
        ▼
commit both, in the same PR
```

CI enforces the first half: the **OpenAPI Contract Ratchet** job in
`.github/workflows/test-pipeline.yml` regenerates the schema from the running
app and fails if it differs from the committed `backend/openapi.json`
(`generate_openapi.py --check`). When that job fails, the message is
`backend contract changed; regenerate + review types` — run the two commands
above and commit the results.

## Consuming these types

Reference schemas through the `components` map:

```ts
import type { components } from '@/types/generated/api';

type DocumentStatusResponse = components['schemas']['DocumentStatusResponse'];
```

Migration is **adopt-on-touch**, not a big-bang rewrite: when you next edit a
service or hook whose response type is hand-mirrored, re-point it at the
generated `components['schemas'][...]` type. The first such consumer is
`src/services/documentAnalyticsApi.ts` (`DocumentStatusResponse`), landed with
the ratchet as a proof of the loop.

Tooling ignores this directory: it is excluded from ESLint (`.eslintrc.cjs`)
and Prettier (`.prettierignore`) so regeneration stays byte-for-byte idempotent.
It is intentionally **not** excluded from `tsc`, so the generated types are
type-checked like the rest of the app.
