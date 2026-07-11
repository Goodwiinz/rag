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
   realtime metrics cards. `websocketService.ts` is the thin auth-store wrapper
   that initialises it. Authentication uses the `Sec-WebSocket-Protocol`
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
- `realtime-websocket-service.ts` — realtime collaboration events.

When these overlap enough to consolidate, fold them toward the canonical
`WebSocketManager` rather than adding another parallel client.
