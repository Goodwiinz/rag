# NOUS — Frontend CODEMAP

> Next.js 15 App Router structure, feature index, store slices, services index.
> Last generated: 2026-04-26

## Entry points

| File                    | Purpose                                        |
| ----------------------- | ---------------------------------------------- |
| `app/layout.tsx`        | Root layout — fonts, theme, providers          |
| `app/providers.tsx`     | QueryClient, AuthProvider, ToastProvider       |
| `app/page.tsx`          | Root redirect → dashboard                      |
| `app/not-found.tsx`     | 404 page                                       |
| `frontend/cli/index.ts` | Node.js REPL CLI (`./nous`) — separate package |

## App Router tree (`app/`)

```
app/
  (auth)/
    login/        Sign-in page
    signup/       Registration
  (dashboard)/
    layout.tsx    Shell: sidebar, nav, auth guard
    dashboard/    Overview / home
    chat/         Conversational agent (1,647 LOC page — split pending)
    documents/    Document library + detail view
    entities/     Knowledge graph entity browser (1,179 LOC — split pending)
    projects/     Research projects list + detail (965 LOC — split pending)
    research/     Research assistant (citations, drafts, notes)
    research-engine/  Multi-step pipeline builder
    analytics/    Usage dashboards
    search/       Semantic search
    settings/     User + workspace settings
    arxiv/        arXiv paper search + ingest
    design-system/ Component showcase
    diagnostics/  Retrieval diagnostics
    quality-metrics-demo/  QA demo
  api/            Next.js API routes (minimal — most traffic goes to FastAPI via rewrite)
  globals.css     Tailwind base + CSS variables
  nous-tokens.css NOUS brand tokens (Erebus, Selene, Sol, Helios, Apollo)
```

## `src/` layout

```
src/
  components/
    ui/             shadcn primitives (button, dialog, input, …)
    layout/         Sidebar, nav bar, header shell pieces
    evaluation/     Evaluation god-components (~15,000 LOC — split pending)
    chat/           Chat-specific widgets
    documents/      Document card, uploader
    knowledge-graph/ Graph visualizer
    research/       Citation cards, draft editor
    …               Feature widgets not yet moved to features/
  services/         API + real-time service layer
    api.ts          Primary REST client (keep — used most widely)
    api-client.ts   Alternate client (consolidation target)
    apiClient.ts    Third client (consolidation target)
    typeSafeApiClient.ts  Type-safe wrapper
    websocketService.ts        Chat WebSocket
    realtime-websocket-service.ts  Realtime status (consolidation target)
    realtimeWebSocketService.ts    (consolidation target)
    websocket-client.ts            (consolidation target)
    analytics/      Analytics-specific event clients
    documentService.ts  Document CRUD helpers
    agentChatService.ts  Agent chat helpers
    threadSearchService.ts  Thread search
    … (28 service files total)
  store/            Zustand slices (canonical — retire src/stores/)
    chat-store.ts        Conversation state (1,379 LOC — split pending)
    agentChatStore.ts    Agent streaming state
    llm-chat-store.ts    LLM chat state
    projectChatStore.ts  Project-chat state
    citationStore.ts     Citations
    projectStore.ts      Research projects
    pipelineStore.ts     Pipeline builder
    realtime-store.ts    Document processing progress
    realtimeProcessingStore.ts  (duplicate — consolidation target)
    research-engine-store.ts   Research engine
    sidebar-store.ts     Sidebar open/close
  stores/           LEGACY — retire and redirect imports to store/
  hooks/            Cross-feature React hooks
  lib/              Framework glue (cn, Supabase client, animations)
  types/            Cross-feature TypeScript types
  utils/            Shared utilities (format, string, date)
  contexts/         React contexts (auth, theme)
  providers/        Provider wrappers
  styles/           Additional CSS
```

## API rewrites (Next.js → FastAPI)

Defined in `next.config.js → rewrites()`:

| Next.js path | Destination                                        |
| ------------ | -------------------------------------------------- |
| `/api/v1/*`  | `${BACKEND_URL \|\| NEXT_PUBLIC_API_URL}/api/v1/*` |
| `/api/v2/*`  | `${BACKEND_URL \|\| NEXT_PUBLIC_API_URL}/api/v2/*` |

Set `BACKEND_URL` in env for server-side rewrites. Vercel builds fail if neither `BACKEND_URL` nor `NEXT_PUBLIC_API_URL` is configured, because otherwise all API rewrites would target `http://localhost:8000`. Do NOT set localhost fallbacks in `env:` block — they get baked into the prod bundle.

## Store slices (src/store/)

| File                       | State                                                |
| -------------------------- | ---------------------------------------------------- |
| `chat-store.ts`            | Messages, streaming state, drafts, tool call results |
| `agentChatStore.ts`        | Agent job polling, HITL confirm flow                 |
| `llm-chat-store.ts`        | LLM-direct chat (non-agent)                          |
| `projectChatStore.ts`      | Project-scoped chat                                  |
| `citationStore.ts`         | Citation list, selected citations                    |
| `projectStore.ts`          | Research project CRUD cache                          |
| `pipelineStore.ts`         | Multi-step pipeline wizard state                     |
| `realtime-store.ts`        | Document ingestion progress                          |
| `research-engine-store.ts` | Research engine runs + results                       |
| `sidebar-store.ts`         | Sidebar open/collapsed                               |

## Known deduplication targets

| Concept      | Files                                                                           | Target                     |
| ------------ | ------------------------------------------------------------------------------- | -------------------------- |
| REST client  | `api.ts`, `api-client.ts`, `apiClient.ts`                                       | Keep `api.ts`              |
| WebSocket    | 4 implementations                                                               | Keep `websocketService.ts` |
| Store root   | `src/store/` + `src/stores/`                                                    | Keep `src/store/`          |
| Format utils | `lib/format-utils.ts`, `utils/formatUtils.ts`, `utils/analytics/formatUtils.ts` | `utils/format.ts`          |

## Adding a new feature

1. Create route: `app/(dashboard)/<feature>/page.tsx` — keep it <300 LOC (server component shell).
2. Create feature components: `src/components/<feature>/` or new `src/features/<feature>/` directory.
3. Add store slice if needed: `src/store/<feature>-store.ts` (Zustand).
4. Add service: `src/services/<feature>Service.ts` using the canonical API client (`api.ts`).
5. Add types: `src/types/<feature>.ts` for cross-component shapes.
6. Add tests: `src/components/<feature>/__tests__/` and `src/__tests__/services/`.
