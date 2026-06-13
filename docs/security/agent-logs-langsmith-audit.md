> **Implementation status** — branch `feat/agent-log-audit-hardening`.
>
> **Shipped (quick wins):** LangSmith hide-I/O outside dev + per-env project naming (`configure_langsmith`); per-tenant LangSmith run metadata `{user_id, org_id, thread_id, job_id}` (`jobs.py`, `streaming.py`, `_merge_run_config`); HITL approval audit logs `hitl_interrupt_raised` / `hitl_decision` with PII-scrubbed args (`_nodes_tools.interrupt_node`); server-side `record_token_usage` wiring (both stream paths); SSE `on_tool_start` arg PII redaction; `_sanitize_metadata` "not a scrubber" docstring.
>
> **Deferred (tracked backlog):** durable `agent_hitl_audit` DB table (§4.A sink 3); `redact_pii` wired into tool I/O + Redis job results (§4.B.1); HumanMessage-content redaction pre-graph (§4.B.2); structured authz-denial + KG path-scope logs; loop-exhaustion / reflection-decision / intent-confidence metrics.

# Agent Logs / LangSmith Audit — NOUS Platform

## 1. TL;DR

- **Prometheus is the strong layer**; LangSmith is the weak one. Node latency, tool call/error counts, classifier path, memory hit-rate, and memory relevance score are all well-instrumented (`observability.py:107-181`). LangSmith carries only `intent:*` / `subgraph:*` / `phase:synthesis` tags on the four executor LLM spans.
- **Biggest gap — LangSmith traces are anonymous.** No `user_id`, `org_id`, `job_id`, or `thread_id` is ever written to LangSmith run metadata; the config dicts at `jobs.py:854` and `streaming.py:314` have no `metadata` key (verified). You cannot filter "user X's traces" or "which org drives tool errors" without a post-hoc DB join.
- **Biggest gap — full plaintext reaches LangSmith unredacted.** `LANGCHAIN_TRACING_V2=true` with **no** `LANGCHAIN_HIDE_INPUTS` and no anonymizer (verified absent), so every user prompt, RAG chunk, and tool arg is uploaded verbatim. `redact_pii()` exists and works (emails/phones/SSN/UUID/PG-URL/tokens — `_pii_redact.py:50-66`) but is wired **only** to the two memory-store writes (`_nodes_memory.py:168,208`).
- **Biggest gap — destructive-tool approvals have no durable audit.** No structured log fires at interrupt-raise or decision time; the approve/reject boolean is consumed silently. The trail lives only in TTL'd Redis and transient LangSmith spans (Postgres checkpointer holds state but no actor/decision row).
- **`_sanitize_metadata` is a misnomer trap** — it only converts datetimes to ISO strings (verified `tool_helpers.py:30-46`); it strips no PII/secrets despite the name and its re-export into `execute.py`. Treat it as zero protection.

## 2. What you can audit in LangSmith TODAY

Saved views to create in project `rag-agent` (LangSmith), plus the Prometheus queries that complement them. Only verified-present signals listed.

| Signal | Where (trace field / tag / metric) | How to filter / query |
|---|---|---|
| Intent of each turn | LangSmith tag `intent:research\|writing\|knowledge_graph\|general` on LLM spans (`_nodes_llm.py:344`) | Filter `tag = intent:research`. Saved view per intent. |
| Subgraph path | LangSmith tag `subgraph:research\|writing\|data\|main` (`research_agent.py:151`, `writing_agent.py:143`, `data_agent.py:118`, `_nodes_llm.py:344`) | Filter `tag = subgraph:research` for path-isolated latency. |
| Force-synthesis turns (degraded) | LangSmith tag `phase:synthesis` (`_nodes_llm.py:416`, `research_agent.py:258`) | Filter `tag = phase:synthesis` to isolate loop-exhausted answers. |
| Per-tool spans | LangSmith `run_type=tool`, span `name` = tool name (`_nodes_tools.py:261-263`) | Filter child runs `type=tool`, `name in {ingest_arxiv_papers,create_draft,...}`. Inputs=args, outputs=result. |
| Retrieval spans | LangSmith `run_type=retriever` (`_nodes_rag.py:201-213`) | Filter `type=retriever` for RAG node visibility. |
| Run name per executor LLM call | LangSmith `run_name` = `llm_node:{intent}` / `force_synthesis_node` (`_prompts.py:276-293`) | Group/dashboard by `run_name`. |
| Token usage per turn | **LangSmith only** (auto-captured `usage_metadata` + `ls_model_name` on `on_chat_model_end`); model name reliably present | Open any LLM span → token counts. **Not in Prometheus** (see gaps). |
| Node latency / errors | Prometheus `agent_node_duration_seconds{node,status}`, `agent_error_total{node,error_type}` (`observability.py:107-133`) | `histogram_quantile(0.95, rate(agent_node_duration_seconds_bucket[5m])) by (node)` |
| Tool call volume / failures | Prometheus `agent_tool_calls_total{tool_name,status}`, `agent_tool_errors_total{tool,category}` (`observability.py:114-151`) | `rate(agent_tool_calls_total[5m]) by (tool_name,status)` |
| Classifier path | Prometheus `agent_classifier_source_total{source,intent}` (`observability.py:137-141`, `_nodes_classify.py:124`) | `rate(agent_classifier_source_total[5m]) by (source,intent)` — alert on `source=fallback` spike. |
| Memory recall + relevance | Prometheus `agent_memory_recall_total{outcome}`, `agent_memory_relevance_score_bucket` (`observability.py:155-181`, `_nodes_memory.py:77`) | hit-rate ratio; `histogram_quantile(0.5, agent_memory_relevance_score_bucket)` |
| Lost assistant rows | Prometheus `agent_assistant_persist_failures_total` (`observability.py:166`, `jobs.py:677-681`) | Alert `increase(...[1h]) > 0`. |
| HITL ownership mismatch | structlog `"HITL ownership mismatch"` (`jobs.py:1059-1064`, `streaming.py:649-654`) | Grep; fields: job_id, owner, requester. Cross-user resume attempts. |
| Per-turn token (client) | SSE `event: usage` (`streaming.py:522-526`) | Client/session logs only — not server-side metric. |

**Note on `error runs` / `high-token runs` / `loop-exhaustion runs` views:** error runs and high-token runs are filterable in LangSmith via span status and the auto-captured token usage. **A `user_id`/`org_id`/`thread_id`/`job_id` saved view is NOT possible today** — those fields are not in run metadata (gap §3). A dedicated `loop-exhaustion` metric/tag does not exist beyond the `phase:synthesis` tag.

## 3. Gaps worth closing

Sorted by corrected severity (verdicts trusted over original claims; refuted gaps dropped; the original "model name not attached" gap is downgraded to **low** since LangSmith auto-captures `ls_model_name` — effectively already-covered for LangSmith, only the Prometheus `record_token_usage` call is missing).

| Gap | Sev | Category | Evidence (file:line) | Fix |
|---|---|---|---|---|
| Full plaintext prompts, RAG chunks, tool args reach LangSmith unredacted (no `LANGCHAIN_HIDE_INPUTS`, no anonymizer) | **critical** | privacy | `observability.py:21-61` (tracing on, no filter — verified); `_nodes_llm.py:273-278` (RAG text in system prompt); `jobs.py:804-812`, `streaming.py:290-311` (raw `HumanMessage`) | `LANGCHAIN_HIDE_INPUTS/OUTPUTS=true` for non-dev in `configure_langsmith()`, **or** anonymizer hook + `redact_pii` on message content pre-`ainvoke`. |
| No durable DB audit row for HITL approvals — trail is TTL Redis + transient traces only | **high** (was critical; checkpointer holds *state* not actor/decision) | audit | no `hitl_audit`/`approval` migration in `alembic/versions/` or `src/migrations/`; `jobs.py:878-887` (Redis-only) | New `agent_hitl_audit` table (spec §4). Checkpointer (`checkpointer.py:60-73`) is *not* a substitute — no actor/decision columns. |
| Raw conversation messages serialized into LangSmith node I/O unredacted (up to 32k chars/msg) | **high** | privacy | `_nodes_memory.py:168` (redact scope = memory only); `streaming.py:290-311`, `jobs.py:805-812` | Apply `redact_pii()` to `HumanMessage.content` before `initial_state`, or RunTree output filter. |
| No `user_id`/`org_id`/`thread_id`/`job_id` in LangSmith run metadata | **high** | who/what | `jobs.py:854-862`, `streaming.py:314-322` (no `metadata` key — verified); `_prompts.py:276-293` (only run_name+tags) | Add `config['metadata']={user_id,org_id,thread_id,job_id}` in both paths; extend `_merge_run_config` to forward `metadata`. |
| `record_token_usage` defined but **zero callers** — no token cost in Prometheus; async path discards `usage={}` | **high** | cost | `observability.py:249` (def); zero callers (verified); `streaming.py:336-393,522-526` (SSE only); `jobs.py:938,1139` (`usage={}` — verified) | Call `record_token_usage(model, in, out)` after stream loop (`streaming.py:~522`) and after `ainvoke` (`jobs.py:~934`); parse `final_state` usage on job path. |
| No structured log when `interrupt()` raised (tool, args, owner never logged) | **high** (was critical) | audit | `_nodes_tools.py:67-101` (no logger); `research_agent.py:295-329` | `logger.info('hitl_interrupt_raised', ...)` (spec §4). |
| Approve/reject decision never logged (who/which tool/decision) — job & stream paths | **high** | audit | `execute.py:383-434`; `streaming.py:581-820`, `:672`; `jobs.py:1099-1103` | `logger.info('hitl_decision_received'...)` / `'hitl_stream_decision'` (spec §4). |
| Destructive tool args stored unfiltered in Redis + LangSmith spans (`_sanitize_metadata` ≠ scrubber) | **high** | privacy | `tool_helpers.py:30-46` (datetime-only — verified); `jobs.py:879-887`; `_nodes_tools.py:261-263` | `_scrub_destructive_args()` (spec §4). |
| HITL resume metadata: no `user_id`/`org_id`/`confirmed` tag on resume invocation | **high** | who/what | `jobs.py:854-862`, `streaming.py:314-322` | Same `metadata` fix + `config['tags']=['hitl_resume','confirmed'\|'rejected']` in `_resume_agent_graph` (`jobs.py:1039`). |
| Authz denials returned as opaque dicts — no structured log at decision point | **high** | who/what | `tools_impl.py:1275,1401,1453,1598,1771,2088` (no logger before `access denied` return) | `logger.warning('agent_authz_denied', {tool,user_id,org_id,resource_type,resource_id})` before each return. |
| KG intermediate-node org scoping (commit `0a8d8dee`) silently applied — path-pruning not logged | **high** | who/what | `knowledge_graph_service.py` `find_paths`/`get_neighborhood`; `tools_impl.py:1988-2020` (no `filtered_by_org`) | `logger.info('kg_path_scope_applied', {org_id,scoped_count,unscoped_count})` when pruning occurred; or add `cross_tenant_paths_pruned` to payload. |
| `_sanitize_metadata` misnamed — false-safety; re-exported into `execute.py` | **medium** | privacy | `tool_helpers.py:30-46`; `execute.py:73-77` | Rename → `_coerce_metadata_for_json`; add `redact_pii` pass on tool-result strings before Redis persist (`jobs.py:956-964`). |
| `_pii_redact` not wired into tool span I/O | **medium** | privacy | `_nodes_tools.py:261-263`; `_pii_redact.py` present but unused in tool path | Apply redactor to `result_content` before LangSmith captures it. |
| `on_tool_start` SSE forwards raw tool args (≤500 chars) to browser, no scrub | **medium** | privacy | `streaming.py:396-398, 712-714` | `args_preview = redact_pii(str(tool_input)[:500])`. |
| iteration_ledger writes unredacted query/messages/tool args to disk | **medium** | privacy | `iteration_ledger.py:103-138,153-157` | Apply `redact_pii` in `_serialize_message`, `user_query`, tool-call args. (Mitigated: gated on `AGENT_LEDGER_DIR`, off by default.) |
| LangSmith `run_id` hardcoded `''` — can't deep-link a turn to its trace | **medium** | who/what | `trace_context.py:12`; `streaming.py:324-331` | Capture `run_id` from first `on_chain_start`; pass to `build_trace_payload`; log via structlog. |
| `org_id` absent from any observability label (cross-tenant alerting impossible) | **medium** | who/what | `observability.py:100-151` (no org dimension) | **Not** Prometheus (cardinality) — use LangSmith metadata + a structlog tool-exec event (`user_id,org_id,tool,status,duration_ms`). |
| `track_node_execution` logs raw `str(e)` (may embed query/DB fragments) | **medium** | privacy | `observability.py:217-221` | `logger.error('Node %s failed after %.2fs', node, dur, exc_info=True)` — drop `%s/e` interpolation. |
| Loop exhaustion has no counter/tag (degraded turns invisible at scale) | **high** | cost/quality | `_nodes_llm.py:375-441` (no helper); no `AGENT_LOOP_EXHAUSTION` in `observability.py` | Add counter `agent_loop_exhaustion_total{intent,subgraph}`; tag `phase:loop_exhausted` at `_nodes_llm.py:416`. |
| Reflection revise/proceed has no counter | **high** | cost/quality | `reflection.py:567-598,453-565` (no helper) | Add `agent_reflection_decision_total{decision,severity,intent}` in `reflection_node`. |
| Project name hardcoded `'rag-agent'`, no env differentiation | **medium** | hygiene | `observability.py:43-48`; `docker-compose.development.yml:70` | `project=f'rag-agent-{DEPLOY_ENV}'` (spec §5). |
| `_nodes_rag.py` warnings log `str(exc)` inline (query may leak) | **low** | privacy | `_nodes_rag.py:286,338` | `exc_info=True`, static message. (Partial: most upstream exceptions don't carry the query.) |
| Missing-org (`organization_id=None`) tool calls not logged | **low** | who/what | `tools_impl.py:1825-1826,1888,1958,2031` (silent `Authentication required`) | `logger.warning('agent_tool_missing_org', ...)` before each return. (Partial: already increments `agent_tool_errors_total`.) |
| `intent_confidence` has no histogram | **low** | quality | `iteration_ledger.py:189`; `_nodes_classify.py:128` | Add `agent_intent_confidence{intent,source}` histogram. |

## 4. Implementation specs (build now)

### A. Destructive-tool approval trail

Goal: a queryable, durable answer to *"who approved which destructive tool with what args, when, and was it approved or rejected."* Destructive tools = `ingest_arxiv_papers`, `create_project`, `create_project_note`, `create_draft` (+ `execute_code`, `forget_memory`).

**Three sinks, one shared payload.** Emit all three at each moment; never rely on Redis or LangSmith alone.

**Shared scrubbed-args helper** — add to `tool_helpers.py` (this is the PII-safety mechanism for the whole trail):
```python
_SENSITIVE_KEYS = {"content", "text", "body", "abstract", "note", "theme", "summary"}
def _scrub_destructive_args(tool_name: str, args: dict) -> dict:
    out = {}
    for k, v in (args or {}).items():
        if k in _SENSITIVE_KEYS:
            out[k] = "[REDACTED]"
        elif isinstance(v, str):
            out[k] = redact_pii(v)[:200]      # PII patterns + length cap
        else:
            out[k] = v
    return out
```
Use it everywhere args are persisted/traced, so the audit row, the structlog event, the Redis confirmation record, **and** the LangSmith tool span all carry the same scrubbed dict.

**Fields (every sink):** `actor_user_id`, `org_id`, `tool_names: list[str]`, `tool_args_scrubbed: jsonb`, `decision: approve|reject|null`, `thread_id`, `job_id`, `timestamp` (ISO/UTC), `outcome` (filled post-exec).

**Sink 1 — structlog (immediate, grep-able):**
- At interrupt raise — `_nodes_tools.py:~87` (before `interrupt(confirmation_details)`) and mirror in `research_agent.py:~313`:
  `logger.info('hitl_interrupt_raised', extra={user_id, org_id, thread_id, tools=[tc['name'] for tc in destructive_calls], tool_args=[_scrub_destructive_args(tc['name'], tc['args']) for tc in destructive_calls]})`
  (user/org from `config['configurable']['current_user']`.)
- At decision — confirm endpoint `execute.py:~427` (after `_validate_confirmable_job`, before `add_task`): `logger.info('hitl_decision_received', extra={user_id, org_id, job_id, confirmed, tool_names})`. Mirror in SSE path `streaming.py` between ownership check (`:655`) and `Command(resume=...)` (`:672`): `logger.info('hitl_stream_decision', ...)`.

**Sink 2 — LangSmith run tags/metadata** (so a trace is filterable by decision): in `_resume_agent_graph` (`jobs.py:1039`) and the SSE resume config (`streaming.py:314`):
```python
config['metadata'] = {'user_id': str(current_user.id), 'org_id': str(current_user.organization_id),
                      'thread_id': request.thread_id or job_id, 'job_id': job_id, 'confirmed': confirmed}
config['tags'] = ['hitl_resume', 'confirmed' if confirmed else 'rejected']
```
Pass scrubbed args (not raw) as the input to `_ls_traceable` in `_nodes_tools.py:261-263`.

**Sink 3 — durable DB row** (survives Redis TTL + LangSmith retention). New Alembic migration:
```sql
agent_hitl_audit(
  id uuid pk, user_id uuid not null, org_id uuid not null,
  thread_id text not null, job_id text,
  tool_names text[], tool_args_scrubbed jsonb,
  confirmed boolean,                       -- null until decided
  raised_at timestamptz not null, decided_at timestamptz, resumed_at timestamptz,
  outcome text)                            -- ok | error | <tool error category>
```
- **INSERT** at interrupt-raise (`confirmed=NULL`, `raised_at=now()`) — co-located with the `hitl_interrupt_raised` log.
- **UPDATE** at decision (`confirmed=bool`, `decided_at=now()`) in the confirm endpoint / SSE resume.
- **UPDATE** `outcome`/`resumed_at` after the resumed `ainvoke` returns (reuse the tool-status the metrics path already classifies).
Index `(org_id, raised_at)` and `(user_id, raised_at)` for tenant audits.

**Files to touch:** `_nodes_tools.py` (interrupt_node) + `subgraphs/research_agent.py` (research_interrupt_node); `tool_helpers.py` (`_scrub_destructive_args`); `api/agent/execute.py` (confirm endpoint); `api/agent/streaming.py` (`stream_confirm_event_generator`); `api/agent/jobs.py` (`_resume_agent_graph`, Redis store at `:879`); new `alembic/versions/*_agent_hitl_audit.py` + a small write helper.

### B. Broaden PII redaction

`redact_pii()` is correct and tested (`_pii_redact.py:50-66`: PG-URL, token, GitHub PAT, email, phone, SSN, UUID — verified) but scoped to memory writes only. Extend to every other sink:

1. **Tool I/O before LangSmith** — in `_execute_single_tool` (`_nodes_tools.py`), run `_scrub_destructive_args` on inputs and `redact_pii` over string values of `result_content` *before* it becomes the `_ls_traceable` span output and before it lands in the Redis job result (`jobs.py:956-964`). This is the single highest-value redaction wire-up.
2. **Message content before the graph runs** — apply `redact_pii` to each `HumanMessage.content` when building `initial_state` (`streaming.py:~290`, `jobs.py:~805`), since LangGraph serializes the whole message list into trace I/O.
3. **SSE `on_tool_start` args** — `streaming.py:397` and `:713`: `args_preview = redact_pii(str(tool_input)[:500])`.
4. **Exception logs** — `observability.py:217` and `_nodes_rag.py:286,338`: switch to `exc_info=True` + static message (keep traceback for operators, keep `str(e)` out of the indexed primary log field).
5. **iteration_ledger** — apply `redact_pii` in `_serialize_message` / `user_query` / tool-call args (`iteration_ledger.py:106,116,156`).

**LangSmith-side global hook (defense in depth):** the code-side redaction above is per-pattern and reliable for SSN/credentials, but it can't catch free-text PII (names, addresses). Add a tracer-level guard in `configure_langsmith()`:
- **Blunt (ship first):** `os.environ.setdefault('LANGCHAIN_HIDE_INPUTS','true')` and `…HIDE_OUTPUTS='true'` for non-dev — strips all I/O; you keep tags/metadata/latency/tokens. (Currently **neither is set** — verified.)
- **Surgical (if you need to keep trace content):** register a LangSmith anonymizer / `RunTree` output-filter that runs `redact_pii` on inputs/outputs before upload.
- **Rename `_sanitize_metadata` → `_coerce_metadata_for_json`** and add a docstring line "NOT a PII scrubber" so no future caller mistakes it for one.

**Risk if skipped:** LangSmith currently holds full academic queries, document excerpts, project names, note bodies, and any user-typed emails/phones/SSNs in plaintext, retained under the LangSmith org's default window, visible to every member of that LangSmith workspace — with **no per-user attribution** to even scope a deletion request. That is an unbounded data-exposure surface outside your tenancy controls.

## 5. LangSmith hygiene

- **Project separation per env.** Today the default is a single hardcoded `'rag-agent'` (`observability.py:43-48`) and `docker-compose.development.yml:70` defaults dev to the same name — dev/staging/prod traces co-mingle. Fix: `project = f'rag-agent-{os.environ.get("DEPLOY_ENV","dev")}'` → `rag-agent-dev` / `rag-agent-staging` / `rag-agent-prod`. Set `LANGCHAIN_PROJECT=rag-agent-dev` explicitly in dev compose; document in `.env.example` (currently the line is commented out, no per-env guidance).
- **Retention.** Set the LangSmith retention window deliberately per project; until §4.B ships, prod content is the riskiest. Short retention on `rag-agent-prod` is a cheap interim mitigation while redaction lands.
- **Who-can-see-traces.** Anyone in the LangSmith workspace sees full trace I/O. Restrict workspace membership; do not invite non-engineers while inputs are unhidden. Once `user_id`/`org_id` metadata exists (§3), you can build the per-user/per-org saved views that scope investigations and support a "show me everything for org X" deletion path.
- **Enable the anonymizer?** Yes for prod — but as defense-in-depth *behind* code-side `redact_pii`, not instead of it (the anonymizer is best-effort on free text; your regex set is the reliable layer for SSN/credentials/PG-URLs). If you only do one thing first, set `LANGCHAIN_HIDE_INPUTS=true` for non-dev.

## 6. Quick wins vs larger work

**Quick wins (hours, low risk, high leverage):**
- Set `LANGCHAIN_HIDE_INPUTS/OUTPUTS=true` for non-dev in `configure_langsmith()` — closes the critical leak in one line.
- Add `config['metadata'] = {user_id, org_id, thread_id, job_id}` at `jobs.py:854` + `streaming.py:314` — unlocks every per-user/per-org/per-thread LangSmith saved view at once.
- Suffix project name with `DEPLOY_ENV` (`observability.py:43`) + dev compose default.
- The two HITL decision-point logs (`hitl_interrupt_raised`, `hitl_decision_received`/`hitl_stream_decision`) and the authz-denial log — pure additive `logger.info/warning` calls.
- Wire `record_token_usage(...)` at the two existing accumulation points (`streaming.py:~522`, `jobs.py:~934`) — token cost into Prometheus.
- `redact_pii(str(tool_input)[:500])` on the two `on_tool_start` SSE lines; `exc_info=True` swap in `observability.py:217` and `_nodes_rag.py:286,338`.
- Rename `_sanitize_metadata` → `_coerce_metadata_for_json` + docstring.

**Larger work (design + migration + tests):**
- `agent_hitl_audit` table + Alembic migration + insert/update wiring across interrupt/confirm/resume (the durable approval trail — spec §4.A).
- `_scrub_destructive_args` + redactor wired into `_execute_single_tool` tool I/O and Redis job results (touches the hot tool path; needs tests so it doesn't break tool outputs).
- `_merge_run_config` extension to forward a `metadata` dict, then thread `user_id`/`org_id`/`thread_id` into per-node and per-tool LangSmith spans.
- New quality metrics: `agent_loop_exhaustion_total`, `agent_reflection_decision_total`, `agent_intent_confidence` histogram (+ Grafana panels/alerts).
- LangSmith `run_id` capture → `build_trace_payload` deep-link + structlog correlation.
- KG path-scope observability (dual scoped/unscoped count or `cross_tenant_paths_pruned` in payload) — requires touching `knowledge_graph_service.find_paths`/`get_neighborhood`.
