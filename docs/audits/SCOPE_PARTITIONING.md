# Scope partitioning for multi-agent audits

One dependency map, one ownership assignment, one cross-boundary reviewer.
Partitioning happens ONCE, before any agent dispatch.

## Process

1. **Dependency map.** From the pinned SHA (never the mutable checkout), list
   scoped files and their import edges. Group into clusters that touch each
   other; clusters become agent scopes.
2. **Ownership assignment.** Every file gets exactly ONE owner agent. Files
   spanning two clusters (wire formats, shared types, protocol constants) are
   owned by the producing side and listed in the other side's `contract_files`
   — read-only context, not audit targets.
3. **Validate** with `python scripts/audit/partition_check.py <partition.json>`.
   Overlap exits non-zero. Fix before dispatch.
4. **Cross-boundary reviewer.** After owners report, ONE reviewer agent receives
   all scope boundaries (the `contract_files` lists) plus every owner's finding
   list, and audits only the seams: producer/consumer frame agreement, enum and
   event-name drift, seq/id semantics across sides.

## partition.json schema

```json
{
  "scopes": [
    {
      "name": "sse-endpoint",
      "own": ["backend/src/api/agent/streaming.py"],
      "contract_files": ["backend/src/services/agent/run_event_types.py"]
    },
    {
      "name": "fe-pipeline",
      "own": ["frontend/src/hooks/chat/useChatStreaming.ts"],
      "contract_files": ["backend/src/services/agent/run_event_types.py"]
    }
  ]
}
```

`own` entries are globs relative to repo root. A file matched by two scopes'
`own` patterns is an overlap error. `contract_files` may repeat across scopes —
that is their purpose (shared seam definitions).

## Streaming audit case study (2026-08-24 postmortem)

Four agents burned 549K input tokens / 184 tool calls; 17 files were read by
two agents each (`agentChatService.ts`, `streaming.py` frame-emitters,
`run_event_types.py`, markdown renderers were the worst overlaps).

Corrected partition:

| Scope | Owner | Owns | Reads as contract |
|-------|-------|------|-------------------|
| SSE endpoint | sse-agent | streaming.py, stream_buffer.py, threads/stream.py | run_event_types.py |
| Services | svc-agent | job_store.py, execution service stream paths, observability.py, _prompts.py, run_event_types.py | streaming.py emit sites |
| FE pipeline | fe-pipe-agent | useChatStreaming.ts, agentChatStore.ts, agentChatService.ts | run_event_types.py |
| FE consumers | fe-ui-agent | reasoning/retrieval/activity components, artifact tree, markdown utils, draft rail | agentChatStore.ts public API |
| Seams | reviewer (after all) | none | all four contract lists + findings |

The reviewer owns every cross-side question ("does the backend's rag_context
shape match what AuiMessage.tsx dereferences?") so owners never need each
other's files.
