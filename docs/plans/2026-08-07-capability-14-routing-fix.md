# Capability-14 Project-Management Routing Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the multi-step project-management flow (create project → add document → create note → list documents) completable from a single agent route, so the `agent-project-management-v1` Harbor eval records reward 1.

**Architecture:** The four tools are split across the RESEARCH and WRITING subgraphs, and routing is single-shot, so no specialist route holds all four. Fix it *symmetrically* — cross-bind the project-CRUD tools so both RESEARCH and WRITING can complete the whole flow — and add a classifier few-shot so multi-action instructions land somewhere capability-complete. All authz stays tool/service-level (unchanged); HITL is registry-derived (automatic from `policy_tags`).

**Tech Stack:** Python 3.11, LangGraph, FastAPI, pytest. Backend venv: `/Users/goodwiinz/development/RAG_system/backend/.venv/bin`.

**Model roles (per session request):**
- **Planning / review:** Fable (already produced the adversarial review this plan encodes).
- **Coding each task:** Sonnet 5.
- **Verification between tasks + final:** Opus 5.

**Why symmetric, not one-directional (Fable finding 1 — HIGH):** `_prompts.py:86-88` `ACTION_INTENT_OVERRIDES` routes `"create a project"` / `"create project"` / `"new project"` → **research @ 1.0**, deterministic, before any threshold. Binding project-create into WRITING only would still fail for the trivially-reworded "Create a project named X…". So RESEARCH must also gain `create_project_note`.

**Why the prompts must change too (Fable finding 2 — HIGH):** HITL and the filtered tool node derive from the registry, so no second gate needs editing — but `AGENTS_writing.md` and `AGENTS_research.md` statically enumerate "Your tools", and the subgraph loop protocol is what the model actually follows. A tool bound but unlisted risks never being called.

**Out of scope (explicitly):** the subgraph→general escalation hatch (Fable: real parent-graph machinery for a hole two small edits close). Not built here.

---

## Pre-flight (Opus, once, before Task 1)

Confirm the baseline is green so later failures are attributable to this change.

Run:
```bash
cd /Users/goodwiinz/development/rag-wt-capfix/backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/services/test_agent_tool_registry.py \
  tests/services/agent/test_writing_subgraph_tools.py \
  tests/unit/services/test_subgraph_factory.py \
  tests/unit/services/test_agent_llm_tool_binding.py -q -p no:cacheprovider
```
Expected: all pass.

---

## Task 1: Cross-bind the three project-CRUD tools in the registry

**Files:**
- Modify: `backend/src/services/agent/tools.py:924-967` (three `ToolDescriptor` blocks)

**Position slots (verified free):** WRITING uses 0–8 → next free are **9, 10**. RESEARCH uses 0–7 → next free is **8**. The registry validator (`tool_registry.py:126-142`) requires one unique position per subgraph and fails loudly on a duplicate, so a wrong slot cannot pass silently.

**Step 1: Write the failing test**

Append to `backend/tests/services/agent/test_writing_subgraph_tools.py`:

```python
def test_project_crud_reachable_from_writing() -> None:
    """capability-14: writing must be able to complete the full flow."""
    from src.services.agent.subgraphs.writing_agent import (
        WRITING_DESTRUCTIVE_TOOLS,
        WRITING_TOOL_NAMES_LIST,
    )

    for name in ("create_project", "add_document_to_project"):
        assert name in WRITING_TOOL_NAMES_LIST, f"{name} missing from writing"
        # destructive tag must carry over so HITL still fires
        assert name in WRITING_DESTRUCTIVE_TOOLS, f"{name} lost HITL in writing"


def test_project_crud_reachable_from_research() -> None:
    """capability-14 symmetric half: research must also be able to note."""
    from src.services.agent.subgraphs.research_agent import (
        RESEARCH_DESTRUCTIVE_TOOLS,
        RESEARCH_TOOL_NAMES_LIST,
    )

    assert "create_project_note" in RESEARCH_TOOL_NAMES_LIST
    assert "create_project_note" in RESEARCH_DESTRUCTIVE_TOOLS
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/goodwiinz/development/rag-wt-capfix/backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_writing_subgraph_tools.py::test_project_crud_reachable_from_writing \
  tests/services/agent/test_writing_subgraph_tools.py::test_project_crud_reachable_from_research \
  -q -p no:cacheprovider
```
Expected: FAIL — `create_project missing from writing`.

**Step 3: Write minimal implementation**

In `tools.py`, edit the three descriptors. `create_project` (924-930):

```python
        ToolDescriptor(
            name="create_project",
            tool=create_project,
            intents=frozenset({AgentIntent.RESEARCH, AgentIntent.GENERAL}),
            # WRITING too: a note/draft needs a project that may not exist yet,
            # and writing is a legitimate route for "create a project and note
            # it" (agent-project-management-v1). Cross-binding keeps the flow
            # completable from either specialist route regardless of how the
            # classifier splits it. HITL is unchanged — DESTRUCTIVE below drives
            # the interrupt in both subgraphs via the registry.
            subgraphs=frozenset({AgentSubgraph.RESEARCH, AgentSubgraph.WRITING}),
            subgraph_positions=(
                (AgentSubgraph.RESEARCH, 4),
                (AgentSubgraph.WRITING, 9),
            ),
            policy_tags=frozenset({ToolPolicyTag.DESTRUCTIVE}),
        ),
```

`add_document_to_project` (953-959):

```python
        ToolDescriptor(
            name="add_document_to_project",
            tool=add_document_to_project,
            intents=frozenset({AgentIntent.RESEARCH, AgentIntent.GENERAL}),
            # WRITING too — same flow: attach the seed document before noting it.
            subgraphs=frozenset({AgentSubgraph.RESEARCH, AgentSubgraph.WRITING}),
            subgraph_positions=(
                (AgentSubgraph.RESEARCH, 6),
                (AgentSubgraph.WRITING, 10),
            ),
            policy_tags=frozenset({ToolPolicyTag.DESTRUCTIVE}),
        ),
```

`create_project_note` (961-967):

```python
        ToolDescriptor(
            name="create_project_note",
            tool=create_project_note,
            intents=frozenset({AgentIntent.WRITING, AgentIntent.GENERAL}),
            # RESEARCH too: ACTION_INTENT_OVERRIDES routes "create a project"
            # to research at 1.0, so the note step must be reachable there or a
            # research-routed project-management turn dead-ends (Fable finding 1).
            subgraphs=frozenset({AgentSubgraph.WRITING, AgentSubgraph.RESEARCH}),
            subgraph_positions=(
                (AgentSubgraph.WRITING, 1),
                (AgentSubgraph.RESEARCH, 8),
            ),
            policy_tags=frozenset({ToolPolicyTag.DESTRUCTIVE}),
        ),
```

**Step 4: Run test to verify it passes**

Run the Step-2 command. Expected: PASS (both).

**Step 5: Commit**

```bash
cd /Users/goodwiinz/development/rag-wt-capfix
git add backend/src/services/agent/tools.py backend/tests/services/agent/test_writing_subgraph_tools.py
git commit -m "feat(agent): cross-bind project CRUD so one route completes capability 14"
```

---

## Task 2: Update the pinned registry-parity test

**Files:**
- Modify: `backend/tests/unit/services/test_agent_tool_registry.py` — `expected_subgraphs` set-equality (281-322) AND the ordered `descriptors_for_subgraph("research")` assertion (330+)

This test asserts **exact** subgraph membership (`==`, not `issubset`), so Task 1 breaks it by design. Update it to the intended new surface — do NOT loosen `==` to `issubset`.

**Step 1: Run to confirm the expected break**

Run:
```bash
cd /Users/goodwiinz/development/rag-wt-capfix/backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/services/test_agent_tool_registry.py -q -p no:cacheprovider
```
Expected: FAIL — the `research`/`writing` sets no longer match.

**Step 2: Update the sets**

In `expected_subgraphs`, add `"create_project_note"` to the `research` set, and add `"create_project"` + `"add_document_to_project"` to the `writing` set. Then update the ordered-list assertion for `descriptors_for_subgraph("research")` to append the tools at their new positions (position order: research gains `create_project_note` at 8, i.e. last).

> Executor note (Sonnet): run the failing assertion first and read the actual-vs-expected diff pytest prints — it names the exact missing/extra members and the exact order. Transcribe from that, do not hand-guess the ordered list.

**Step 3: Run to verify pass**

Run the Step-1 command. Expected: PASS.

**Step 4: Commit**

```bash
git add backend/tests/unit/services/test_agent_tool_registry.py
git commit -m "test(agent): update registry parity for cross-bound project CRUD"
```

---

## Task 3: Update the two subgraph driver prompts

**Files:**
- Modify: `backend/src/services/agent/subgraphs/AGENTS_writing.md` (Your tools, ~5-13)
- Modify: `backend/src/services/agent/subgraphs/AGENTS_research.md` (Your tools, ~5-12)

**Step 1: Write the failing test**

Append to `backend/tests/services/agent/test_writing_subgraph_tools.py`:

```python
def test_writing_prompt_lists_project_creation() -> None:
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    prompt = load_agents_md("writing")
    assert "create_project" in prompt
    assert "add_document_to_project" in prompt


def test_research_prompt_lists_note_creation() -> None:
    from src.services.agent.subgraphs.agents_md_loader import load_agents_md

    prompt = load_agents_md("research")
    assert "create_project_note" in prompt
```

**Step 2: Run to verify it fails**

Run:
```bash
cd /Users/goodwiinz/development/rag-wt-capfix/backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_writing_subgraph_tools.py::test_writing_prompt_lists_project_creation \
  tests/services/agent/test_writing_subgraph_tools.py::test_research_prompt_lists_note_creation \
  -q -p no:cacheprovider
```
Expected: FAIL.

**Step 3: Edit the prompts**

In `AGENTS_writing.md`, under `## Your tools`, add two bullets (after `create_project_note`):

```markdown
- `create_project` — create a new project (folder) when the user asks to make one before noting into it. Requires a name. Destructive — gated by user confirmation.
- `add_document_to_project` — attach an existing document (by `document_id`) to a project. Destructive — gated by user confirmation.
```

And extend the step-4 loop guidance with one line so the model sequences create→attach→note when the project does not yet exist:

```markdown
   - If the user asks to **create a project and then note into it**, and no such project exists, call `create_project` first, then `add_document_to_project` for any named document, then `create_project_note`. Each is confirmed separately.
```

In `AGENTS_research.md`, under `## Your tools`, add:

```markdown
- `create_project_note` — write a note into a project. Destructive — gated by user confirmation.
```

**Step 4: Run to verify pass**

Run the Step-2 command, plus the prompt-content regression already in the file:
```bash
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/services/agent/test_writing_subgraph_tools.py -q -p no:cacheprovider
```
Expected: PASS (all, including `test_writing_prompt_documents_title_resolution`).

**Step 5: Commit**

```bash
git add backend/src/services/agent/subgraphs/AGENTS_writing.md \
        backend/src/services/agent/subgraphs/AGENTS_research.md \
        backend/tests/services/agent/test_writing_subgraph_tools.py
git commit -m "docs(agent): list cross-bound project tools in subgraph driver prompts"
```

---

## Task 4: Clear the stale "research-only" comment on ingest_arxiv_papers

**Files:**
- Modify: `backend/src/services/agent/tools.py:239-244` (the `project_id` Field description)

After Task 1, `create_project` is no longer research-only, so the comment's premise is false and would mislead the next reader.

**Step 1: Edit**

Replace the comment block in the `Field(description=...)` (239-244) with:

```python
        Field(
            description=(
                "UUID of an existing project, as returned by list_projects. "
                "NOT the project name — a name is rejected."
            )
```

(Drop the stale "Deliberately does not name create_project…" note entirely — it no longer holds.)

**Step 2: Verify nothing referenced it**

Run:
```bash
cd /Users/goodwiinz/development/rag-wt-capfix
grep -rn "research-only" backend/src/services/agent/tools.py
```
Expected: no hit tied to create_project.

**Step 3: Commit**

```bash
git add backend/src/services/agent/tools.py
git commit -m "docs(agent): drop stale research-only note now that create_project is cross-bound"
```

---

## Task 5: Add the multi-action classifier few-shot

**Files:**
- Modify: `backend/src/services/agent/classifier.py` — `_CLASSIFIER_SYSTEM_PROMPT` few-shot block (~139-165)

Belt-and-suspenders (Fable finding 8): even with Task 1, teach the taxonomy that multi-action project instructions are a general/project-management shape, so the healthy LLM path stops over-committing to `writing`. This is what run 3 (0.62 writing) exposed.

**Step 1: Write the failing test**

Append to `backend/tests/unit/services/test_agent_classifier.py` (inside the fallback test class or a new one):

```python
    async def test_multi_action_project_instruction_prompt_has_example(self):
        """The classifier prompt must teach the multi-action shape so the
        healthy LLM path stops over-routing capability-14 to writing."""
        from src.services.agent.classifier import _CLASSIFIER_SYSTEM_PROMPT

        p = _CLASSIFIER_SYSTEM_PROMPT.lower()
        assert "add" in p and "note" in p and "project" in p
        # an explicit multi-step example, not just the words scattered
        assert "then" in p
```

**Step 2: Run to verify it fails or is weak**

Run:
```bash
cd /Users/goodwiinz/development/rag-wt-capfix/backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest \
  tests/unit/services/test_agent_classifier.py -k multi_action -q -p no:cacheprovider
```
Expected: FAIL (no such example yet).

**Step 3: Add the few-shot**

In `_CLASSIFIER_SYSTEM_PROMPT`, after the "Search our docs for RLHF" example, add:

```
Query: "Create a project named X, add the paper titled Y to it, write a note in it, then list its documents"
→ intent: general, confidence: 0.9, reasoning: "Multi-step project management spanning create + attach + note + list — needs the full tool set, which only the general route binds."
```

And under `## Common confusions`, add:

```
- Multi-step "create a project AND add/note/list" → general (spans research + writing tools; a single specialist route is missing some)
```

**Step 4: Run to verify pass**

Run the Step-2 command. Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/services/agent/classifier.py backend/tests/unit/services/test_agent_classifier.py
git commit -m "feat(agent): teach classifier that multi-action project instructions are general"
```

---

## Task 6: Full regression (Opus verification gate)

**Step 1: Run the backend unit + services suites**

Run:
```bash
cd /Users/goodwiinz/development/rag-wt-capfix/backend
/Users/goodwiinz/development/RAG_system/backend/.venv/bin/python -m pytest tests/unit tests/services -q -p no:cacheprovider
```
Expected: all pass (baseline was 3962 passed / 77 skipped on develop; expect ≥ that plus the new tests, 0 failures).

**Step 2: Lint the changed files**

Run:
```bash
V=/Users/goodwiinz/development/RAG_system/backend/.venv/bin
$V/black --check backend/src/services/agent/tools.py backend/src/services/agent/classifier.py \
  backend/tests/services/agent/test_writing_subgraph_tools.py \
  backend/tests/unit/services/test_agent_tool_registry.py \
  backend/tests/unit/services/test_agent_classifier.py
$V/isort --check-only backend/src/services/agent/tools.py backend/src/services/agent/classifier.py
```
Expected: clean.

**Step 3: Do NOT commit if red.** Fix and re-run.

---

## Task 7: End-to-end proof — re-run the Harbor eval (Opus, manual gate)

The unit tests prove the binding; only a real run proves the *flow* completes with 3 HITL approvals. This is the acceptance criterion for the whole plan.

**Prerequisite:** Docker running; `doctl registry login` done; backend image `registry.digitalocean.com/ragsystemregistry/backend:3a436b2-r1` pulled `--platform linux/amd64`.

**Dev-faithful credentials** (established this session — `/do-kb` is dev's real source; CHAT overridden to the live pod value):

```bash
# Build a throwaway verify tree = eval task (#1354) + this fix, both in one context
git worktree add -b bench/capfix-verify /Users/goodwiinz/development/rag-wt-capfix-verify pr-1354
cd /Users/goodwiinz/development/rag-wt-capfix-verify
git merge --no-edit origin/fix/project-crud-both-subgraphs

infisical run --env=dev --path=/do-kb --silent -- \
  env AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5.6-luna \
  harbor run \
    --path evals/agent-project-management-v1 \
    --agent-import-path evals.harbor_agents.nous_production_agent:NousProductionAgent \
    --env docker --jobs-dir evals/jobs \
    --job-name agent-project-management-v1-capfix \
    --force-build --n-concurrent 1 --yes
```

**Expected:** `Reward 1.0 / Count 1`, 0 exceptions. If reward 0, read
`evals/jobs/agent-project-management-v1-capfix/*/verifier/audit.json` `failures[]`
and `agent/evidence.json` (`classification`, `milestones`, `tool_executions`) —
do NOT patch the verifier to pass; a red verifier here is signal.

**On green:** capture the run to record the #1354 baseline (`benchmarks[]`,
`recorded_at`, `repository_revision` = the merged develop SHA once this lands).

---

## Merge order (all PRs from this session)

1. **#1357** (`reasoning_effort` default → `none`) — prerequisite for any luna repoint.
2. **This branch** `fix/project-crud-both-subgraphs` — the capability-14 fix.
3. **#1356** (weak-keyword floor) — independent; LLM-outage hygiene, not the cap-14 fix. Land anytime.
4. **#1355** (synthesis effort knob) — rebase after #1357 (same config block + test file conflict).
5. **#1354** (the eval task + baseline) — LAST, so `repository_revision` pins a real merged develop SHA that already contains the fix, and the recorded run is a pass.

---

## Notes for the executor

- **Do not touch authz.** Fable confirmed all project-ownership checks are tool/service-level (`_verify_project_ownership` inside each tool impl; `create_project` → `_ensure_workspace_owned`), subgraph-independent. Cross-binding changes reachability, not tenancy. Adding a check "to be safe" would be duplicate logic.
- **Do not build the escalation hatch.** Out of scope by decision.
- Reference @superpowers:executing-plans for the task-by-task loop and @superpowers:test-driven-development for the red-green discipline.
