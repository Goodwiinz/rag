# Memory Tier B Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the privacy + UX + insight-extraction gap on the agent's long-term memory subsystem after Tier A landed (save-gate, provenance, semantic index).

**Architecture:** Three additive features on top of the shipped `_nodes_memory.py` + `memory.py` foundation. (1) Regex-redact emails/phones/UUIDs at save time so stored memories never expose PII. (2) Expose a `forget_memory(query)` agent tool that fuzzy-deletes by semantic match — destructive, gated via HITL `interrupt()`. (3) Wire the orphan `extract_insights` LLM helper into the save path so real user preferences land alongside raw query echoes. Each feature is independently testable + reversible via env flag.

**Tech Stack:** Python 3.12, LangGraph `AsyncPostgresStore` (semantic index over Cohere embeddings), LangChain `@tool` for the new agent tool, pytest with `@pytest.mark.unit` markers. No new dependencies.

---

## Pre-flight

**Branch:** `feat/agent-memory-tier-b` (cut from `feat/do-kb-activation` once Tier A + T2.1 land on origin).

**Files you will touch** (canonical list — read-only audit them first if you're new to this codebase):

- `backend/src/services/agent/_nodes_memory.py` (165 lines today; save gate + provenance already in place)
- `backend/src/services/agent/memory.py` (containing `_build_memory_index_config`, store init, `save_memory`, `search_memories`)
- `backend/src/services/agent/memory_store.py` (orphan today — `extract_insights` lives here; you will partially wire it in)
- `backend/src/services/agent/tools.py` (registers all 12 agent tools; you will add `forget_memory`)
- `backend/src/api/agent/tools_impl.py` (the actual handlers behind `@tool` definitions)
- `backend/src/services/agent/_nodes_tools.py` (`DESTRUCTIVE_TOOLS` set — add `"forget_memory"`)
- `backend/src/core/config.py` (env knobs)
- `backend/tests/services/agent/` (new test files)

**Reusable utilities to KNOW before editing** (search them with `grep -n`):

- `memory.py:_build_memory_index_config()` — returns the Cohere embedder config or `None`. Reuse for any new code that needs `(text → vector)`.
- `memory.py:get_memory_store()` — singleton AsyncPostgresStore. Always go through this; never construct your own.
- `memory_store.py:extract_insights(messages, config) -> list[str]` — already-built LLM helper, currently unused. You will call it from `memory_save_node`.
- `_nodes_tools.py:DESTRUCTIVE_TOOLS` — destructive set the HITL gate consults. Adding here is how a tool gets pre-execution confirmation.
- `observability.py:record_memory_recall(hit, max_score)` — extend, don't duplicate.

**Skills to consult if blocked:**

- `superpowers:test-driven-development` — every step writes the failing test first.
- `superpowers:systematic-debugging` — when a test won't fail or won't pass, work the 4-phase loop, don't guess.
- `superpowers:verification-before-completion` — never call a task done without seeing the assertions pass on a fresh run.

---

## Task 1 — PII redaction at save

**Why:** Trace evidence (P4.x audit) showed raw `query[:200]` saved to memory, including emails / phone numbers / UUIDs / DB connection strings users had pasted. After P4.2 added semantic recall, those PII strings now influence ranking → privacy + GDPR liability.

**Files:**

- Create: `backend/src/services/agent/_pii_redact.py`
- Modify: `backend/src/services/agent/_nodes_memory.py:430-440` (right before `save_memory()` call)
- Test: `backend/tests/services/agent/test_pii_redact.py`

**Step 1.1 — Write the failing unit test for the redactor**

Create `backend/tests/services/agent/test_pii_redact.py`:

```python
"""PII redactor strips emails, phones, UUIDs from memory values."""
from __future__ import annotations

import pytest

from src.services.agent._pii_redact import redact_pii


@pytest.mark.unit
class TestRedactPII:
    def test_strips_email(self):
        assert redact_pii("contact me at jane@example.com please") == (
            "contact me at <email> please"
        )

    def test_strips_phone_us(self):
        assert redact_pii("call +1-415-555-0123 today") == (
            "call <phone> today"
        )

    def test_strips_uuid(self):
        assert redact_pii(
            "project 5ed25258-5ad2-4b06-9678-4a4abe5ecac1 is active"
        ) == "project <uuid> is active"

    def test_strips_postgres_url(self):
        text = (
            "DB is postgresql://user:secret@host.example.com:5432/db?sslmode=require"
        )
        assert redact_pii(text) == "DB is <postgres-url>"

    def test_passthrough_clean_text(self):
        assert redact_pii("find papers on transformers") == (
            "find papers on transformers"
        )

    def test_empty_input(self):
        assert redact_pii("") == ""
        assert redact_pii(None) == ""
```

**Step 1.2 — Run the test, verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/services/agent/test_pii_redact.py -v
```

Expected: `ModuleNotFoundError: src.services.agent._pii_redact`

**Step 1.3 — Implement the redactor**

Create `backend/src/services/agent/_pii_redact.py`:

```python
"""Regex PII redactor for memory values.

Run on every string we are about to persist to the long-term memory
store. Replaces emails, phone numbers, UUIDs, and postgres connection
strings with bracketed sentinels so the literal value never ends up
in the recall index.

Intentionally conservative — false positives (a UUID-shaped string in
prose) are cheap; false negatives (a real email stored verbatim) cost
us GDPR posture.
"""

from __future__ import annotations

import re
from typing import Final

_EMAIL_RE: Final = re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
# US-ish phone with optional country code + separators.
_PHONE_RE: Final = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)
_UUID_RE: Final = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
# postgres://user:pass@host:port/db or postgresql:// variant.
_PG_URL_RE: Final = re.compile(r"\bpostgres(?:ql)?://\S+\b")


def redact_pii(text: str | None) -> str:
    """Return *text* with emails, phones, UUIDs, and PG URLs replaced."""
    if not text:
        return ""
    out = _PG_URL_RE.sub("<postgres-url>", text)
    out = _EMAIL_RE.sub("<email>", out)
    out = _PHONE_RE.sub("<phone>", out)
    out = _UUID_RE.sub("<uuid>", out)
    return out


__all__ = ["redact_pii"]
```

**Step 1.4 — Run the test, verify it passes**

```bash
.venv/bin/python -m pytest tests/services/agent/test_pii_redact.py -v
```

Expected: 6 passed.

**Step 1.5 — Write the failing integration test (gate → save → no PII in value)**

Append to `backend/tests/services/agent/test_memory_save_gating.py`:

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_saved_value_strips_pii_from_query():
    """save_memory writes a redacted query string, not the raw input."""
    save_mock = AsyncMock(return_value=True)
    store = MagicMock()
    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock):
        await memory_save_node(
            _state(
                intent="research",
                messages=[
                    HumanMessage(
                        content=(
                            "email me at jane@example.com about project "
                            "5ed25258-5ad2-4b06-9678-4a4abe5ecac1"
                        )
                    ),
                    AIMessage(content="..."),
                ],
                tool_executions=[{"tool_name": "search_arxiv"}],
            ),
            _config(),
        )
    save_mock.assert_called_once()
    value = save_mock.call_args.args[3]
    assert "jane@example.com" not in value["query"]
    assert "5ed25258" not in value["query"]
    assert "<email>" in value["query"]
    assert "<uuid>" in value["query"]
```

**Step 1.6 — Run it, verify it fails**

```bash
.venv/bin/python -m pytest tests/services/agent/test_memory_save_gating.py::test_saved_value_strips_pii_from_query -v
```

Expected: FAIL — saved value still has raw email + UUID.

**Step 1.7 — Wire redactor into save path**

Edit `backend/src/services/agent/_nodes_memory.py`. Find the block that builds the `value` dict (around `last_user_content[:200]`). Modify imports + the `query` field:

```python
# Add to imports near top
from src.services.agent._pii_redact import redact_pii
```

Replace:

```python
"query": last_user_content[:200],
```

with:

```python
"query": redact_pii(last_user_content)[:200],
```

**Step 1.8 — Run the test, verify it passes**

```bash
.venv/bin/python -m pytest tests/services/agent/test_memory_save_gating.py -v
```

Expected: all 5 (or 4 plus the new one) pass.

**Step 1.9 — Re-run the full agent suite to catch regressions**

```bash
.venv/bin/python -m pytest tests/services/agent/ -x -q -k "not integration and not e2e and not deepeval and not langsmith"
```

Expected: all pass.

**Step 1.10 — Commit**

```bash
git add backend/src/services/agent/_pii_redact.py \
        backend/src/services/agent/_nodes_memory.py \
        backend/tests/services/agent/test_pii_redact.py \
        backend/tests/services/agent/test_memory_save_gating.py
git commit -m "fix(agent): redact emails / phones / UUIDs / PG URLs from memory values

Trace evidence in the Tier A audit showed raw user queries persisted
to long-term memory, including pasted emails, phone numbers, project
UUIDs, and full postgres connection strings. After P4.2 wired Cohere
semantic recall, those strings became part of the ranking signal —
both a leakage risk and a GDPR posture problem.

_pii_redact.redact_pii runs over query text at save time and replaces
matches with <email> / <phone> / <uuid> / <postgres-url> sentinels.
Intentionally conservative regexes — false positives are cheap, false
negatives are not.

Tests: 6 redactor unit tests + 1 end-to-end save-gate integration test."
```

---

## Task 2 — `forget_memory` agent tool (HITL-gated)

**Why:** Today the agent can save memories but cannot delete them. Users have already asked the agent to "forget what I told you about X" and seen no effect. Exposing a tool fixes UX + closes the GDPR right-to-erasure loop. Destructive → must go through the existing `interrupt()` HITL gate.

**Files:**

- Modify: `backend/src/services/agent/tools.py` (add `@tool forget_memory`)
- Modify: `backend/src/api/agent/tools_impl.py` (add handler)
- Modify: `backend/src/services/agent/_nodes_tools.py:56` (add `"forget_memory"` to `DESTRUCTIVE_TOOLS`)
- Modify: `backend/src/services/agent/memory.py` (add `delete_memory_by_query()`)
- Test: `backend/tests/services/agent/test_forget_memory.py` (new)

**Step 2.1 — Failing test for the delete-by-query helper**

Create `backend/tests/services/agent/test_forget_memory.py`:

```python
"""forget_memory deletes the closest semantic match from the user's store."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agent.memory import delete_memory_by_query


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_memory_returns_deleted_count():
    store = MagicMock()
    matched_item = MagicMock(key="abc123", score=0.92)
    matched_item.value = {"query": "find papers on transformers"}
    store.asearch = AsyncMock(return_value=[matched_item])
    store.adelete = AsyncMock(return_value=None)

    out = await delete_memory_by_query(
        store, user_id="user-1", query="papers on transformers", limit=3
    )

    assert out["deleted"] == 1
    assert out["matches"][0]["key"] == "abc123"
    store.adelete.assert_awaited_once_with(("user", "user-1"), "abc123")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_delete_memory_skips_low_score_match():
    """A match with score < 0.6 is reported but NOT deleted (avoid accidents)."""
    store = MagicMock()
    weak = MagicMock(key="xyz", score=0.4)
    weak.value = {"query": "something else"}
    store.asearch = AsyncMock(return_value=[weak])
    store.adelete = AsyncMock(return_value=None)

    out = await delete_memory_by_query(
        store, user_id="user-1", query="papers", limit=3
    )

    assert out["deleted"] == 0
    assert out["matches"][0]["score"] == 0.4
    store.adelete.assert_not_awaited()
```

**Step 2.2 — Run, verify fail**

```bash
.venv/bin/python -m pytest tests/services/agent/test_forget_memory.py -v
```

Expected: `ImportError: cannot import name 'delete_memory_by_query'`.

**Step 2.3 — Implement helper in `memory.py`**

Append to `backend/src/services/agent/memory.py`:

```python
# Minimum similarity score before forget_memory will actually delete.
# Trace 019e040b style false-recalls (score ≈ 0.06) would otherwise let
# a stray "forget" request wipe an unrelated memory. 0.6 is empirical —
# tune if FN/FP rate is wrong after deploy.
_FORGET_SCORE_THRESHOLD: float = 0.6


async def delete_memory_by_query(
    store,
    user_id: str,
    query: str,
    limit: int = 3,
) -> dict:
    """Find the top semantic matches for *query* under the user's namespace,
    delete those above the safety threshold, and return a report.

    Returns ``{"deleted": int, "matches": [{key, score, query}]}``.
    """
    if store is None or not query:
        return {"deleted": 0, "matches": []}

    namespace = ("user", user_id)
    try:
        results = await store.asearch(namespace, query=query, limit=limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning("forget_memory: asearch failed: %s", exc)
        return {"deleted": 0, "matches": []}

    matches = [
        {
            "key": item.key,
            "score": float(getattr(item, "score", 0.0) or 0.0),
            "query": (getattr(item, "value", None) or {}).get("query", ""),
        }
        for item in results
    ]

    deleted = 0
    for m in matches:
        if m["score"] >= _FORGET_SCORE_THRESHOLD:
            try:
                await store.adelete(namespace, m["key"])
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "forget_memory: adelete failed for %s: %s", m["key"], exc
                )

    return {"deleted": deleted, "matches": matches}
```

**Step 2.4 — Verify the unit tests pass**

```bash
.venv/bin/python -m pytest tests/services/agent/test_forget_memory.py -v
```

Expected: 2 passed.

**Step 2.5 — Failing test for the agent tool surface**

Append to `backend/tests/services/agent/test_forget_memory.py`:

```python
@pytest.mark.unit
def test_forget_memory_is_destructive_tool():
    from src.services.agent._nodes_tools import DESTRUCTIVE_TOOLS

    assert "forget_memory" in DESTRUCTIVE_TOOLS


@pytest.mark.unit
def test_forget_memory_tool_registered():
    from src.services.agent.tools import ALL_TOOLS

    assert any(t.name == "forget_memory" for t in ALL_TOOLS), (
        "forget_memory must be registered in ALL_TOOLS so subgraphs can bind it"
    )
```

**Step 2.6 — Run, verify both fail**

```bash
.venv/bin/python -m pytest tests/services/agent/test_forget_memory.py::test_forget_memory_is_destructive_tool tests/services/agent/test_forget_memory.py::test_forget_memory_tool_registered -v
```

**Step 2.7 — Register the tool**

Edit `backend/src/services/agent/tools.py`. Look at how `create_project_note` is registered (a near-shape match: takes a string, dispatches to `tools_impl`, marked destructive). Mirror that pattern for `forget_memory`. Skeleton:

```python
@tool(parse_docstring=True)
async def forget_memory(
    query: str,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """Forget previously-saved memories that match *query*.

    Use when the user explicitly asks you to forget, delete, or wipe a
    memory ("forget what I said about X", "stop remembering Y"). Returns
    a summary of which memories were deleted.

    Args:
        query: A short description of the memory to forget.

    Returns:
        ``{"deleted": int, "matches": [{key, score, query}]}``.
    """
    from src.api.agent.tools_impl import _tool_forget_memory

    page_ctx = _read_page_context(config)
    user_id = _read_user_id(config)
    return await _tool_forget_memory(
        query=query, user_id=user_id, page_context=page_ctx
    )
```

(Adjust to the exact decorator + helper names used in the file. Use the existing `create_project_note` entry as a template.)

Add `forget_memory` to the `ALL_TOOLS` registration at the bottom of `tools.py`.

**Step 2.8 — Implement the handler in `tools_impl.py`**

Append to `backend/src/api/agent/tools_impl.py`:

```python
async def _tool_forget_memory(
    *,
    query: str,
    user_id: str,
    page_context: dict | None = None,
) -> dict:
    """Handler for the forget_memory agent tool."""
    if not user_id:
        return {"error": "forget_memory: missing user_id from config"}
    if not query or not query.strip():
        return {"error": "forget_memory: empty query"}

    from src.services.agent.memory import (
        delete_memory_by_query,
        get_memory_store,
    )

    store = await get_memory_store()
    if store is None:
        return {"error": "forget_memory: memory store unavailable"}

    result = await delete_memory_by_query(
        store, user_id=user_id, query=query, limit=5
    )
    return {
        "status": "completed",
        "deleted": result["deleted"],
        "matches": result["matches"],
    }
```

**Step 2.9 — Add to `DESTRUCTIVE_TOOLS`**

Edit `backend/src/services/agent/_nodes_tools.py:56`. Append `"forget_memory"` to the set:

```python
DESTRUCTIVE_TOOLS = {
    "ingest_arxiv_papers",
    "add_document_to_project",
    "create_project",
    "create_project_note",
    "create_draft",
    "execute_code",
    "forget_memory",
}
```

Also append to each subgraph's destructive set if the tool is bound there. Today `forget_memory` only routes through general intent — no subgraph touch needed in this PR.

**Step 2.10 — Run the registration + destructive tests**

```bash
.venv/bin/python -m pytest tests/services/agent/test_forget_memory.py -v
```

Expected: 4 passed.

**Step 2.11 — Verify the HITL gate fires for forget_memory**

Look at `tests/unit/services/test_agent_bugfixes.py::test_should_continue_routes_destructive_to_interrupt` for the pattern. If a parallel test already covers DESTRUCTIVE_TOOLS membership, your set addition is enough; if it's hardcoded, extend it. **Read the test first**, then decide.

**Step 2.12 — Commit**

```bash
git add backend/src/services/agent/memory.py \
        backend/src/services/agent/tools.py \
        backend/src/services/agent/_nodes_tools.py \
        backend/src/api/agent/tools_impl.py \
        backend/tests/services/agent/test_forget_memory.py
git commit -m "feat(agent): expose forget_memory tool with HITL gate + safety threshold

Closes the right-to-erasure loop on the long-term memory subsystem.
Users can now ask the agent to forget specific memories; the agent
calls forget_memory(query=...), which fuzzy-matches against the
user's namespace via the same Cohere index P4.2 wired and deletes
the top results above 0.6 similarity.

Below the threshold the matches are reported but NOT deleted —
trace-019e040b-style false recalls (score ≈ 0.06) would otherwise
let a stray 'forget' request wipe unrelated memories.

Tool is added to DESTRUCTIVE_TOOLS so the existing interrupt() HITL
gate prompts the user before each forget actually fires.

Tests: 4 unit tests covering helper + registration + destructive
membership."
```

---

## Task 3 — Wire `extract_insights` into the save path

**Why:** Today's `memory_save_node` persists raw `{query, intent, tools_used}`. The orphan `memory_store.extract_insights` already builds a lightweight-LLM that distills conversation history into preference-shaped strings ("user prefers IEEE citations", "user works in oncology"). Wiring it gives the recall index something more useful than echoed user input.

**Files:**

- Modify: `backend/src/services/agent/_nodes_memory.py` (extend `memory_save_node`)
- Modify: `backend/src/core/config.py` (add `AGENT_INSIGHT_EVERY_N_TURNS` setting)
- Test: `backend/tests/services/agent/test_memory_insights.py` (new)

**Step 3.1 — Add the env knob**

Edit `backend/src/core/config.py` near the existing `AGENT_*` block:

```python
# Run the insight-extraction pass every N user turns inside memory_save_node.
# 0 disables. Default 5: cheap enough to not bloat token spend, frequent
# enough to keep recall surface useful within a session.
AGENT_INSIGHT_EVERY_N_TURNS: int = 5
```

**Step 3.2 — Failing test for the insight cadence**

Create `backend/tests/services/agent/test_memory_insights.py`:

```python
"""memory_save_node runs extract_insights every N turns when enabled."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.services.agent._nodes_memory import memory_save_node


def _state_with_n_humans(n: int) -> dict:
    msgs: list = []
    for i in range(n):
        msgs.append(HumanMessage(content=f"user msg {i}"))
        msgs.append(AIMessage(content=f"reply {i}"))
    return {
        "messages": msgs,
        "intent": "research",
        "tool_executions": [{"tool_name": "search_arxiv"}],
    }


def _config() -> dict:
    user = MagicMock()
    user.id = "user-1"
    return {"configurable": {"current_user": user, "thread_id": "t-1"}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_insights_extracted_on_5th_turn():
    save_mock = AsyncMock(return_value=True)
    insights_mock = AsyncMock(return_value=["user prefers IEEE citations"])
    store = MagicMock()

    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock), \
       patch(
        "src.services.agent.memory_store.extract_insights",
        new=insights_mock,
    ):
        await memory_save_node(_state_with_n_humans(5), _config())

    # Two saves: one for the raw turn, one per insight emitted.
    assert save_mock.await_count == 2
    insights_mock.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_insights_skipped_on_non_multiple_turn():
    save_mock = AsyncMock(return_value=True)
    insights_mock = AsyncMock(return_value=["nope"])
    store = MagicMock()

    with patch(
        "src.services.agent.memory.get_memory_store",
        new=AsyncMock(return_value=store),
    ), patch("src.services.agent.memory.save_memory", new=save_mock), \
       patch(
        "src.services.agent.memory_store.extract_insights",
        new=insights_mock,
    ):
        await memory_save_node(_state_with_n_humans(3), _config())

    assert save_mock.await_count == 1
    insights_mock.assert_not_awaited()
```

**Step 3.3 — Run, verify both fail**

```bash
.venv/bin/python -m pytest tests/services/agent/test_memory_insights.py -v
```

Expected: FAIL — current `memory_save_node` only runs one save and never calls `extract_insights`.

**Step 3.4 — Implement the insight pass**

Edit `backend/src/services/agent/_nodes_memory.py`. Inside `memory_save_node`, after the existing `await save_memory(...)` call, add:

```python
        # Insight extraction every N turns. Cheap LLM call distills
        # the conversation into preference-shaped strings that are
        # far more useful for future recall than echoed user input.
        from src.core.config import get_settings

        every_n = get_settings().AGENT_INSIGHT_EVERY_N_TURNS
        if every_n > 0 and turn_index > 0 and turn_index % every_n == 0:
            try:
                from src.services.agent.memory_store import extract_insights

                serialised = [
                    {"role": "user" if isinstance(m, HumanMessage) else "assistant",
                     "content": m.content}
                    for m in state["messages"]
                    if getattr(m, "content", "")
                ]
                insights = await extract_insights(serialised, config)
                for i, insight in enumerate(insights):
                    if not insight or len(insight) < 10:
                        continue
                    insight_key = hashlib.md5(
                        f"insight:{turn_index}:{i}:{insight[:60]}".encode(),
                        usedforsecurity=False,
                    ).hexdigest()[:12]
                    await save_memory(
                        store,
                        str(current_user.id),
                        insight_key,
                        {
                            "query": redact_pii(insight)[:300],
                            "intent": "insight",
                            "tools_used": [],
                            "thread_id": thread_id,
                            "turn_index": turn_index,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "memory_type": "insight",
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("insight extraction skipped: %s", exc)
```

Add `from src.services.agent._pii_redact import redact_pii` to imports if not already present from Task 1.

**Step 3.5 — Run the test, verify it passes**

```bash
.venv/bin/python -m pytest tests/services/agent/test_memory_insights.py -v
```

Expected: 2 passed.

**Step 3.6 — Re-run full agent suite**

```bash
.venv/bin/python -m pytest tests/services/agent/ -x -q -k "not integration and not e2e and not deepeval and not langsmith"
```

Expected: all pass.

**Step 3.7 — Commit**

```bash
git add backend/src/services/agent/_nodes_memory.py \
        backend/src/core/config.py \
        backend/tests/services/agent/test_memory_insights.py
git commit -m "feat(agent): wire extract_insights into memory_save_node every N turns

memory_store.extract_insights was already implemented but unused. Today
the recall index only holds {query, intent, tools_used} echoes; after
P4.2 wired Cohere ranking those echoes still rank above truly useful
context.

Every AGENT_INSIGHT_EVERY_N_TURNS turns (default 5), the save path now
distils the conversation via the lightweight LLM into preference-shaped
strings ('user prefers IEEE citations', 'user works in oncology') and
persists each as memory_type='insight' under the same namespace.

Insights pass through redact_pii so emails / phones never end up in
the distilled output either.

Tests: 2 unit tests asserting cadence + skip-when-not-multiple."
```

---

## Task 4 — End-to-end smoke + PR

**Why:** Three independent features just landed. Confirm the agent loop still routes correctly and the memory index can ingest the new shapes.

**Step 4.1 — Run the broader unit suite + e2e c2u harness**

```bash
.venv/bin/python -m pytest tests/services/agent/ tests/unit/services/test_agent_bugfixes.py -x -q \
  -k "not integration and not e2e and not deepeval and not langsmith"
bash scripts/test/e2e_agent_fixes.sh c2u
```

Expected: all pass; harness summary green.

**Step 4.2 — Manual smoke against a running backend (optional but recommended)**

```bash
# After restart with new branch:
# 1. Trigger a save with PII
#    "ingest 2401.12345 for jane@example.com"
# 2. Trigger forget
#    "forget what I told you about ingestion"
# 3. After 5 user turns:
#    confirm memory_save_node emits insight memories
```

Then via LangSmith MCP:

```
mcp__langsmith__fetch_runs project_name=rag-agent-dev limit=3 is_root=true
```

Assertions to read by eye:

- `user_memories[*].value.query` contains `<email>` / `<uuid>` (not the raw values).
- Trace shows `forget_memory` tool span ➝ `interrupt_node` ➝ resume.
- After turn 5, additional save spans with `memory_type=insight`.

**Step 4.3 — Open PR**

```bash
git push -u origin feat/agent-memory-tier-b
gh pr create --base develop --title "feat(agent): memory tier B — PII redact, forget tool, insight extraction" \
  --body "$(cat <<'EOF'
## Summary

Three additive features on the long-term memory subsystem built on top
of the Tier A foundation (save-gate + provenance + Cohere semantic index).

- **Task 1 — PII redaction.** `_pii_redact.redact_pii` strips emails,
  phone numbers, UUIDs, and Postgres connection strings from values
  before save. Closes the privacy hole opened when P4.2 turned raw
  query text into ranking signal.
- **Task 2 — `forget_memory` agent tool.** Fuzzy-matches via the same
  Cohere index, deletes above a 0.6 safety threshold, routes through
  the existing HITL `interrupt_node` because it is destructive.
- **Task 3 — Insight extraction.** Wires the orphan
  `memory_store.extract_insights` helper into `memory_save_node` every
  `AGENT_INSIGHT_EVERY_N_TURNS` turns (default 5). Distilled
  preferences land alongside the raw turn, also passing through
  `redact_pii`.

## Test plan

- [ ] `pytest backend/tests/services/agent/test_pii_redact.py`
- [ ] `pytest backend/tests/services/agent/test_memory_save_gating.py`
- [ ] `pytest backend/tests/services/agent/test_forget_memory.py`
- [ ] `pytest backend/tests/services/agent/test_memory_insights.py`
- [ ] `bash backend/scripts/test/e2e_agent_fixes.sh c2u`
- [ ] Manual: ingest with PII → trace shows redacted save
- [ ] Manual: forget → HITL prompt fires
- [ ] Manual: 5th turn → insight memory persisted with memory_type=insight
EOF
)"
```

---

## Verification cheat sheet

| Feature            | LangSmith assertion                                                                                                        | Prom metric                                                                           |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| PII redact         | `user_memories[*].value.query` contains `<email>` / `<uuid>` sentinels, never raw values                                   | n/a                                                                                   |
| forget_memory      | `tool_executions[*].tool_name == "forget_memory"` followed by `interrupt_node` span; result `{deleted: N, matches: [...]}` | `agent_tool_calls_total{tool_name="forget_memory"}` increments                        |
| insight extraction | After turn ≥5, additional save spans with `value.memory_type == "insight"`                                                 | none yet — out of scope; add `agent_insight_emit_total` only if dashboards request it |

## Open questions for the next session

1. Should `forget_memory` also work on `memory_type="insight"` rows separately, or is one unified match good? Default in this plan: unified.
2. Insight cadence is per-turn — should it also fire on `END` of a thread (session-end summary)? Not in this PR.
3. `_FORGET_SCORE_THRESHOLD = 0.6` is empirical. Capture distribution from `agent_memory_relevance_score` after a week and re-tune.
