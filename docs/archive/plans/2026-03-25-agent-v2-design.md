# Agent v2 Design: Workflow Enhancements

**Date:** 2026-03-25
**Branch:** `feature/agent-v2`
**Approach:** Evolutionary Enhancement — add new nodes to existing StateGraph

---

## Decisions

| Decision        | Choice                                                        |
| --------------- | ------------------------------------------------------------- |
| Scope           | All improvements, phased roadmap                              |
| Deployment      | Single `feature/agent-v2` branch                              |
| Models          | Tiered: gpt-4o-mini (fast/cheap) + gpt-4o (complex reasoning) |
| Memory          | PostgreSQL + Qdrant (semantic retrieval)                      |
| Plan visibility | Adaptive (show for 3+ steps, background for simple)           |

---

## 1. Graph Flow

### Two paths, shared enhancements

**Main graph (outer):**

```
START -> rag_node -> llm_intent_classifier -> memory_retrieval
  -> route_by_intent -> [chosen path] -> memory_save -> END
```

**General path** (route_by_intent -> `llm_node`):

```
adaptive_planner? -> llm_node -> should_continue ->
  | interrupt_node -> (confirmed?) -> tool_node -> context_compactor? -> llm_node (loop)
  | tool_node -> context_compactor? -> llm_node (loop)
  | reflection_gate -> memory_save_node
```

**Subgraph paths** (research, writing, data — each gets the same enhancements internally):

```
adaptive_planner? -> {sub}_llm_node -> {sub}_should_continue ->
  | interrupt_node -> (confirmed?) -> {sub}_tool_node -> context_compactor? -> {sub}_llm_node (loop)
  | {sub}_tool_node -> context_compactor? -> {sub}_llm_node (loop)
  | reflection_gate -> END (compiled subgraph exits to parent node, parent routes to memory_save_node)
```

### Structural decisions

- **Compactor between tool_node -> llm_node**: LLM needs clean context, not raw verbose outputs.
- **Reflection gate on terminal branch**: Where `should_continue` would route to END, first pass through reflection. Max 2 rounds.
- **Planner after routing, inside chosen path**: Planner needs tool subset and prompt context. Runs once per path entry — skipped if `state["plan"]` already populated.
- **Interrupt node added to subgraphs**: Closes the current HITL gap where destructive tools in subgraphs ran without confirmation.
- **Shared utility functions**: `context_compactor`, `reflection_gate`, `interrupt_node` are reusable functions via `make_compactor_node()`, `make_reflection_gate()`, etc.

### State schema additions

```python
class AgentState(TypedDict):
    # ... existing fields ...
    plan: list                # [{step, tool, args_hint}] — advisory, emitted via SSE
    reflection_count: int     # Max 2 per execution, reset to 0 per turn
    compaction_count: int     # Increments each compaction, reset to 0 per turn
    intent_confidence: float  # LLM classifier confidence (0-1)
```

**Reset semantics per user turn:** `plan=[]`, `reflection_count=0`, `compaction_count=0` — reset in `_run_agent_graph` initial state construction. Preserved across tool loops within the same turn.

---

## 2. LLM Intent Classifier

Replaces keyword-weighted `intent_classifier_node` with a structured LLM call.

**Model:** gpt-4o-mini, `temperature=0` (deterministic routing).

**Input:** Last user message + previous assistant turn (if any) + `page_context`. Not the full thread.

**Structured output:**

```python
class IntentClassification(BaseModel):
    intent: Literal["research", "writing", "knowledge_graph", "general"]
    confidence: float  # 0.0 - 1.0
    reasoning: str     # For debugging/LangSmith traces
```

**Fallback:** If confidence < 0.7 -> run keyword matcher -> if keyword matcher has strong winner, use it -> otherwise keep LLM result -> if both ambiguous, default to `general`.

**Classifier prompt includes few-shot examples** for known confusions:

- "graph neural networks" -> research (not knowledge_graph)
- "extract entities from this paper" -> knowledge_graph
- "summarize the relationship between papers" -> writing

**New `_build_classifier_llm()` helper** targeting gpt-4o-mini deployment (separate from `_build_llm()` which targets gpt-4o).

`route_by_intent` stays unchanged — only the classification logic changes.

---

## 3. Structured Error Recovery

### Error taxonomy

| Category       | Examples                                            | Recovery                                                                                                                   |
| -------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `transient`    | Network timeout, 429, temporary API failure         | Auto-retry inside `_execute_single_tool` with exponential backoff (3 attempts, 1s/2s/4s). Does not increment `error_count` |
| `recoverable`  | Document not found, wrong ID, missing prerequisite  | Structured hint to LLM: `{"error", "error_type": "recoverable", "suggestion": "..."}`. Increments `error_count`            |
| `user_fixable` | Permission denied, org mismatch, missing API key    | LLM-mediated (reads suggestion, asks user naturally). Increments `error_count`                                             |
| `fatal`        | Invalid tool name, schema violation, internal crash | Return error, increment `error_count`. At 3 consecutive fatals, terminate                                                  |

### Implementation

- **Transient retry inside `_execute_single_tool`** — explicit loop, not `_RETRY_POLICY` (which only wraps `rag_node`/`llm_node`).
- **`user_fixable` stays LLM-mediated** — no reuse of `interrupt_node` (which only handles destructive-action confirmation).
- **`_classify_error` handles both exceptions AND returned `{"error": ...}` payloads** — two code paths, one taxonomy.
- **`last_error` stays `str`** for logging. New `last_error_info: dict` holds `{category, message, suggestion}`.
- **Consecutive error counter** — `error_count` resets to 0 after any successful tool call. Max 3 consecutive non-transient errors terminates.

**Per-tool suggestion map:**

```python
TOOL_ERROR_HINTS = {
    ("add_document_to_project", "not_found"): "The document must be ingested first. Use ingest_arxiv_papers.",
    ("ingest_arxiv_papers", "timeout"): "Try fewer papers (max 3 at a time).",
    ("search_arxiv", "no_results"): "Try broader search terms or different keywords.",
    ...
}
```

---

## 4. Adaptive Planner

### When it fires

After routing, inside the chosen path. **Runs once per path entry** — if `state["plan"]` is already populated, skip both complexity check and plan generation.

**Complexity check** (gpt-4o-mini, `temperature=0`):

```python
class ComplexityCheck(BaseModel):
    step_count: int  # Estimated tool calls needed
```

If `step_count >= 3`, run the planner. Otherwise proceed directly to `llm_node`.

**Input:** Last user message + `page_context` + available tool names for this path.

### Plan format

```python
class PlanStep(BaseModel):
    step: int
    description: str      # "Search arXiv for transformer papers"
    tool: str             # "search_arxiv"
    args_hint: dict       # {"query": "transformer architectures"}
    depends_on: list[int] # [1, 2]

class AgentPlan(BaseModel):
    steps: list[PlanStep]
    reasoning: str
```

**Model:** gpt-4o for plan generation (needs reasoning quality).

### Usage

**Advisory only.** The plan is:

1. Stored in `state["plan"]` for trace/debug visibility
2. Emitted as SSE `plan` event for frontend display
3. Injected as compact summary in system prompt: `"Suggested plan: 1) Search arXiv... 2) Ingest top 5... 3) Add to project"`

Only injected while `state["plan"]` is non-empty. LLM is free to deviate.

### Not yet implemented

- No `plan_step_index` (advisory only, no plan-following state machine)
- No replanning after failures (LLM handles recovery via error suggestions)
- No user approval of plans (HITL only fires for destructive tools)

---

## 5. Context Compactor

### Trigger

**Based on estimated token size, not message count.** Estimate tokens across all ToolMessages (`len(content) // 4`). Threshold: compact when total ToolMessage tokens exceed ~8000 (configurable).

### Target selection

Scan backward from end of `state["messages"]` to find the most recent AIMessage with `tool_calls` and all its corresponding ToolMessages. That batch is protected. Everything older is a compaction candidate.

**Skip already-compacted messages** — compacted ToolMessages have `[Compacted]` prefix.

### Compaction process

1. **Extract IDs deterministically** — regex for UUIDs and arXiv IDs from original content
2. **LLM summarization** — gpt-4o-mini, `temperature=0`, prompt: preserve IDs/titles/status codes, remove verbose content, under 200 tokens
3. **Validate** — assert all extracted IDs appear in compacted output. If missing, append: `"Referenced IDs: [...]"`
4. **Replace** — emit new ToolMessage with same `id` and `tool_call_id` as original. LangGraph accumulator replaces in-place.

### State changes

```python
return {"messages": replacement_messages, "compaction_count": state["compaction_count"] + 1}
```

---

## 6. Reflection Gate

### When it fires

Terminal branch of `should_continue` (no more tool calls). Only for `research` and `writing` intents. Guard: `reflection_count < 2`.

**Model:** gpt-4o-mini, `temperature=0`.

**Input:** Last AIMessage + original user message + `state["plan"]` if present.

**Structured output:**

```python
class ReflectionResult(BaseModel):
    passed: bool
    issues: list[str]
    severity: Literal["none", "minor", "major"]
```

### Evaluation criteria

**Research:** Did tools execute? Are document IDs real? Full request addressed?
**Writing:** Sources referenced? Output substantive? Format matches request?

### Routing

- `passed` or `severity == "minor"` -> proceed to END / `memory_save_node`
- `severity == "major"` and `reflection_count < 2` -> route back to `llm_node` with SystemMessage: "Your response had these issues: {issues}. Please revise."
- `reflection_count >= 2` -> proceed regardless

### Not included

- No reflection on general/knowledge_graph intents
- No user-facing indication (invisible quality improvement)

---

## 7. Persistent Memory (PostgreSQL + Qdrant)

### Schema

```sql
CREATE TABLE agent_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    organization_id UUID NOT NULL,
    content TEXT NOT NULL,
    memory_type VARCHAR(50),
    embedding_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT now(),
    last_accessed_at TIMESTAMPTZ,
    access_count INT DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_agent_memories_user ON agent_memories(user_id);
CREATE INDEX idx_agent_memories_org ON agent_memories(organization_id);
```

### Write path (memory_save_node)

1. Extract insights (gpt-4o-mini, `temperature=0`)
2. Insert via fresh `AsyncSessionLocal()`
3. Embed with sentence-transformers -> index in Qdrant `agent_memories` collection (scoped by `user_id`)

### Read path (memory_retrieval_node)

1. Embed user query -> semantic search in Qdrant (filtered by `user_id`)
2. Hydrate from PostgreSQL
3. Top 5 -> inject into system prompt

### Decay

Memories not accessed in 90 days soft-deleted via scheduled task.

---

## 8. SSE & Frontend Changes

### New SSE events

| Event        | Payload                   | When                                    |
| ------------ | ------------------------- | --------------------------------------- |
| `plan`       | `{steps, reasoning}`      | After planner generates 3+ step plan    |
| `reflection` | `{passed, issues, round}` | After reflection gate (debug, hideable) |

### Deliverables

1. **Backend `event_generator`** — emit `plan` and `reflection` events
2. **`agentChatService.ts`** — add `plan` and `reflection` cases to SSE switch
3. **`agentChatStore.ts`** — new state: `currentPlan: PlanStep[] | null`, cleared on `done`
4. **UI component** — collapsible "Plan" card with step status (pending/active/done) based on `tool_start`/`tool_end` matching

---

## 9. Code Reorganization

### Split execute.py (~2500 lines)

| New file          | Contents                                              | ~Lines |
| ----------------- | ----------------------------------------------------- | ------ |
| `execute.py`      | API endpoints only                                    | ~400   |
| `tools_impl.py`   | All `_tool_*` functions + dispatcher                  | ~800   |
| `tool_helpers.py` | ID resolution, ownership checks, error classification | ~300   |
| `streaming.py`    | `event_generator`, SSE, stream confirm                | ~400   |
| `jobs.py`         | Job storage, TTL cleanup, `_run_agent_graph`          | ~300   |

### New feature files

| File                               | Contents                                         |
| ---------------------------------- | ------------------------------------------------ |
| `services/agent/classifier.py`     | LLM intent classifier, `_build_classifier_llm()` |
| `services/agent/planner.py`        | Complexity check, plan generation                |
| `services/agent/compactor.py`      | Token estimation, ID extraction, compaction      |
| `services/agent/reflection.py`     | Reflection prompt, routing                       |
| `services/agent/memory_store.py`   | PostgreSQL + Qdrant memory                       |
| `services/agent/error_recovery.py` | `ToolError`, `_classify_error`, retry logic      |

### Migration

- Alembic migration for `agent_memories` table
- Startup check for `agent_memories` Qdrant collection

---

## 10. Testing Strategy

| Layer              | What                    | How                                                                            |
| ------------------ | ----------------------- | ------------------------------------------------------------------------------ |
| Classifier         | Intent accuracy         | Parametrized: `("graph neural networks", "research")`, etc.                    |
| Compactor          | ID preservation         | Verbose ToolMessage -> compact -> assert UUIDs/arXiv IDs survive               |
| Planner            | Complexity gating       | Simple -> no plan. Complex -> 3+ steps                                         |
| Reflection         | Pass/fail routing       | Bad response -> routes back. Good -> passes. Max 2 respected                   |
| Error recovery     | Category classification | Timeout -> transient. Not found -> recoverable. Permission -> user_fixable     |
| Memory             | Write + read roundtrip  | Save -> embed -> semantic retrieve -> assert match                             |
| Consecutive errors | Reset on success        | 2 errors -> success -> error -> count is 1, not 3                              |
| Integration        | Full graph              | "Find papers on X, add to project" -> plan, tools, reflection, memory all work |
