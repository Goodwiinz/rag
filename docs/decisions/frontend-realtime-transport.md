# Frontend realtime transport rule

Status: accepted (2026-07-11)
Audit: C8 (P5.3) — dead frontend WebSocket clients.

## Context

The `frontend/src/services/` layer accumulated several overlapping WebSocket
implementations. Two of them — `enhancedWebSocket.ts` (`EnhancedWebSocketService`)
and `websocket-client.ts` (`WebSocketClient`) — had **zero non-test production
importers** and no tests. Their own file headers already pointed callers
elsewhere, and the services `README.md` mislabelled `websocket-client.ts` as
"used by monitoring and diagnostics" when monitoring actually runs on its own
`MonitoringWebSocketClient` (`monitoringWebsocketService.ts`). Both dead files
were deleted in the C8 remediation PR.

## Rule

1. **One WebSocket client stack.** New realtime push features go through the
   canonical client, not a new bespoke socket wrapper. Do not add another
   `*WebSocket*` service module for a use case an existing client already covers.

2. **Canonical client = `@/services/websocket` (`WebSocketManager`).** This is
   the client the **live document / processing flows actually use**, via the
   `useWebSocket` hook (`@/hooks/useWebSocket.ts`) and its
   `useDocumentProcessingUpdates` helper — consumed by document upload
   (`hooks/upload/useDocumentUpload.ts`), the processing dashboard, and the
   realtime metrics cards. The `RealtimeProcessingProvider`
   (`components/realtime/RealtimeProcessingProvider.tsx`) constructs the
   `WebSocketManager` from the authenticated Supabase session token +
   `organization_id`, and the `useWebSocket` hook resolves that shared instance
   (`getWebSocketManager()`). Authentication uses the `Sec-WebSocket-Protocol`
   header (`['auth', token]`), never a URL query param.

3. **Topic subscription, not per-connection sockets.** Consumers subscribe to
   typed event topics (e.g. document-processing updates, query-status updates)
   on the shared connection and unsubscribe on unmount. Do not open a fresh
   socket per component or per topic.

4. **REST polling is a fallback only.** Prefer the WebSocket push path for
   realtime state. Fall back to REST polling (e.g. document status polling in
   `documentService.ts`) only when a socket is unavailable or the flow is not
   latency-sensitive.

5. **Agent chat is SSE, not WebSocket.** The LangGraph agent flow streams over
   Server-Sent Events (`agentChatService.ts` / `streamingService.ts`,
   `POST /api/v1/agent/stream`). It is intentionally outside the WebSocket
   stack; do not migrate it onto a socket client.

## Existing specialised clients (leave as-is)

These have real importers and their own domains; they are not part of the
"add a new socket" temptation this rule guards against:

- `monitoringWebsocketService.ts` — admin monitoring feed (`MonitoringWebSocketClient`).
- `realtimeWebSocketService.ts` — workspace realtime service (`useRealtimeProcessing`, `ConnectionManager`).

When these overlap enough to consolidate, fold them toward the canonical
`WebSocketManager` rather than adding another parallel client.

## Convergence status

The goal is one canonical stack plus the small set of genuinely-used specialised
clients above. Progress:

- **Prior C8 remediation** — deleted `enhancedWebSocket.ts` and
  `websocket-client.ts` (zero importers, no tests).
- **Phase 1 (2026-07-12)** — deleted two more fully-dead parallel stacks, each
  with zero live (non-excluded) importers and no tests. Both were already
  quarantined in the tsconfig `exclude` list:
  - `realtime-websocket-service.ts` — its only consumer was `store/realtime-store.ts`,
    whose only consumer was the unmounted duplicate
    `app/components/realtime/RealtimeStatusDashboard.tsx`. All three removed.
    (Not to be confused with the **live** `realtimeWebSocketService.ts`, which
    stays.) This corrected an earlier inaccuracy in this doc, which had listed
    `realtime-websocket-service.ts` under "leave as-is (real importers)" — it had
    none.
  - `websocketService.ts` — an already-`@deprecated` standalone graph-updates
    socket that never touched `WebSocketManager`; its only consumer was the
    unmounted `components/graph/GraphWebSocketProvider.tsx`. Both removed.

Remaining stacks and the order to fold them toward `WebSocketManager` (phase 2+,
**not** done here — both are live and non-trivially consumed):

1. `realtimeWebSocketService.ts` — workspace realtime service; consumed via
   `useRealtimeProcessing` (NotificationCenter, RealtimeStatusDashboard,
   PerformanceMonitor) and `ConnectionManager`. Migrate those consumers onto
   `useWebSocket` topic subscriptions first (medium blast radius).
2. `monitoringWebsocketService.ts` — admin monitoring feed; the largest client,
   with its own auth/reconnect domain. Fold last.
