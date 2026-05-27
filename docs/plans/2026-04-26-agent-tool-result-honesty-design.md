# Agent Tool-Result Honesty — Design

**Date:** 2026-04-26
**Status:** Approved (brainstorm complete; implementing)
**Scope:** Stop the CLI from saying "Actions completed." when a confirmed tool actually did nothing. Two PRs: load-bearing surfacing fix first, optional prompt hardening second.

## Goal

Kill the "Actions completed." lie. Today, a real session saw `ingest_arxiv_papers` return `{status: "ingestion_complete", documents_ingested: 0}` after the agent invented 10 paper IDs, and the CLI cheerfully printed `Actions completed.` because the LLM stayed silent on resume. After this design lands, the CLI prints honest per-tool summaries derived from the actual tool result, and never inserts a generic success line.

## Non-goals

- Per-tool summarizer table. The heuristic covers the high-value tools; everything else falls back to a bare tool name (today's behavior). New tools opt in by adding a `summary` key to their return dict.
- Semantic migration of `is_error`. Tools that return `documents_ingested: 0` keep being "successes" — we just render the count truthfully.
- Behavioral enforcement of the prompt rules. They're guidance; the LLM either follows or doesn't.

## Architecture

Two seams, both small.

1. **Backend SSE result encoding (≈3 lines).** `streaming.py`'s `tool_end` handler currently emits `result: str(output)[:500]`. For dict/list outputs that's Python's `repr`-ish form (single quotes) — unparseable. Switch to `json.dumps(output)[:500]` when the output is a dict or list, falling back to `str(output)` for strings/scalars. The CLI now gets parseable JSON for structured results.

2. **CLI tool-end renderer.** `streamToTerminal`'s `tool_end` branch ignores `event.result`. New helper `formatToolEndLine(tool, result, isError)` produces a single-line summary. The branch calls it when stopping/erroring the spinner. The "Actions completed." line in the `done` branch is deleted entirely — the per-tool summaries carry all the truth the user needs.

The optional follow-up (PR-D-2) layers system-prompt rules on top of the now-honest CLI surface. They're polish, not load-bearing.

## Components

| File                                  | New / Change    | Purpose                                                                                                                                      |
| ------------------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/src/api/agent/streaming.py`  | change          | Encode dict/list `tool_end.result` as JSON instead of `str()`. ~3 lines. Both `stream_event_generator` and `stream_confirm_event_generator`. |
| `frontend/cli/stream.ts`              | change          | Add `result: string` to `StreamEvent.tool_end` shape; parse from SSE payload.                                                                |
| `frontend/cli/repl.ts`                | change          | New `formatToolEndLine()` helper + `pickSummary()` heuristic; tool_end branch consumes them; delete `Actions completed.` filler.             |
| `backend/src/services/agent/graph.py` | change (PR-D-2) | Three new system-prompt rules (honest reporting, project-name disambiguation, /clear handling).                                              |

## Backend SSE result encoding

```python
# streaming.py — both tool_end blocks
output = event.get("data", {}).get("output", "")
is_error = (
    isinstance(output, dict) and bool(output.get("isError"))
) or (
    getattr(output, "status", None) == "error"
)
try:
    if isinstance(output, (dict, list)):
        preview = _json.dumps(output)[:500]
    else:
        preview = str(output)[:500]
except (TypeError, ValueError):
    preview = str(output)[:500]
yield f"event: tool_end\ndata: {_json.dumps({'tool': name, 'result': preview, 'is_error': is_error})}\n\n"
```

The `try/except` catches non-serializable values (e.g. a tool that accidentally returns a `datetime`). Falls back to today's behavior.

## CLI rendering rules

```ts
formatToolEndLine(tool, result, isError):
  parsed = tryJsonParse(result) | null

  // Errors win
  if (isError or (parsed && parsed.error)) {
    msg = parsed?.error ?? truncate(result, 80)
    return `${tool} ✗ ${msg}`        // spinner.error()
  }

  // Empty / no useful payload
  if (!result || result === '{}' || result === '[]') {
    return tool                       // spinner.stop(tool) — same as today
  }

  // Structured success
  if (parsed && typeof parsed === 'object') {
    summary = pickSummary(parsed)
    return summary ? `${tool} · ${summary}` : tool
  }

  // String success
  return `${tool} · ${truncate(result, 80)}`
```

`pickSummary(parsed)` heuristic, in order, first match wins:

1. `parsed.summary` (string) → use it.
2. `parsed.documents_ingested` (number) AND `parsed.paper_ids` (array) → `"${documents_ingested} of ${paper_ids.length} ingested"`.
3. `parsed.total` (number) AND a known plural key in `{papers, projects, documents, notes, drafts}` → `"${total} ${pluralKey}"`.
4. Any `*_id` string key (e.g. `project_id`, `note_id`, `draft_id`) → `"created ${parsed.name ?? id.slice(0,8)}"`.
5. Otherwise → `null` (caller renders bare `tool`).

### Examples

| Today                                             | After                                                     |
| ------------------------------------------------- | --------------------------------------------------------- |
| `ingest_arxiv_papers` ✓ then `Actions completed.` | `ingest_arxiv_papers ✗ Invalid arXiv ID format: ['fake']` |
| `ingest_arxiv_papers` ✓ then `Actions completed.` | `ingest_arxiv_papers · 0 of 10 ingested`                  |
| `list_projects` ✓                                 | `list_projects · 7 projects`                              |
| `create_project` ✓                                | `create_project · created RAG Research`                   |
| `search_arxiv` ✓                                  | `search_arxiv · 5 papers`                                 |
| `add_document_to_project` ✓ (no useful keys)      | `add_document_to_project ✓` _(unchanged)_                 |

## "Actions completed." removal

Delete this branch from `streamToTerminal`'s `done` handler:

```ts
if (inConfirmFlow && !postConfirmTokens) {
  p.log.success("Actions completed."); // ← gone
}
```

The whole `postConfirmTokens` accounting becomes dead and gets removed too. The per-tool summaries from seam 2 are now the user's only "did anything happen?" signal — and they reflect reality.

## Prompt hardening (PR-D-2)

Three additions to `graph.py`'s `llm_node` system prompt block, each ≤2 sentences:

1. **Honest result reporting.** "When a tool returns `documents_ingested: 0`, `total: 0`, or any structured indicator that nothing was added/created, you MUST tell the user explicitly (e.g. 'No papers were ingested — the IDs I tried weren't valid'). Do NOT respond with a generic 'done' or stay silent."
2. **Project-name disambiguation.** "If the user names a project that matches multiple entries (e.g. 'RAG Research' matches both 'RAG Research' and 'RAG Research 2025'), ask which one before acting. Do not silently pick the first match."
3. **`/clear` is a CLI primitive.** "If the user message is exactly `/clear` or asks you to 'clear the chat', reply with one short sentence: 'That's a CLI command — type it at the prompt.' Do NOT pretend you cleared anything."

## Testing strategy

### PR-D-1 (load-bearing)

**`frontend/cli/__tests__/repl.test.ts`** — extend the existing tool_end coverage:

- error path: `tool_end` with `is_error: true` and `result: '{"error":"Invalid X"}'` → spinner errors with `✗ Invalid X`.
- dict-success with `documents_ingested: 0` and `paper_ids` length 10 → spinner stop label includes `0 of 10 ingested`.
- dict-success with `total: 7, projects: [...]` → `7 projects`.
- dict-success with no recognized keys → bare `tool`.
- empty `{}` result → bare `tool`.
- non-JSON string result → `· first 80 chars`.
- Drop the existing `Actions completed.` assertion. Add a regression test that the string is **never** printed.

**`backend/tests/unit/api/test_agent_streaming_json_results.py`** (new, ~3 tests):

- dict output → emits valid JSON in `result` field
- string output → emits raw string
- non-serializable output (e.g. datetime) → falls back to `str()` without crashing

### PR-D-2 (polish)

**`backend/tests/unit/services/test_agent_prompt_rules.py`** (new, ~3 tests):

- assert each new rule string appears in the assembled `llm_node` system prompt for the `general` and `research` intents
- pattern follows the existing `_assert_shared_rules_present` helper in `test_agent_graph_partial.py`

### Manual smoke (PR-D-1, must pass before merge)

1. Force a no-op: confirm an `ingest_arxiv_papers` call with fake IDs (rejected by the validator from `fix/agent-arxiv-id-validation`). Expect `ingest_arxiv_papers ✗ Invalid arXiv ID format: [...]` in place of `Actions completed.`
2. Confirm a real `ingest_arxiv_papers` after `search_arxiv`. Expect `ingest_arxiv_papers · N of M ingested` with real numbers.
3. List projects. Expect `list_projects · 7 projects` or similar count.

## Sequencing

- **PR-D-1** — backend SSE encoding tweak + CLI renderer + delete filler. Independent of polish PR. ~120 lines + ~10 new tests.
- **PR-D-2** — three prompt rules + three rule-presence tests. Independent of PR-D-1; can land any time. ~30 lines.

## Rejected alternatives

**Per-tool summarizer table.** Cleanest output for known tools but requires a code change every time a tool is added. Heuristic + opt-in `summary` key gives 90% of the value with zero ongoing maintenance.

**Strict `is_error` semantic migration.** "Document ingested: 0" should _be_ an error. Most rigorous, but reshaping every tool's success contract is a huge audit, breaks existing callers, and the LLM still needs to interpret the new flag. Not worth the blast radius for a UX fix.

**CLI parses Python repr.** Avoids the backend change but invites bugs. JSON is a 3-line backend tweak; cheaper than a parser.
