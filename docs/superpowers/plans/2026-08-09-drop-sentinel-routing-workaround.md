# Remove the Sentinel-Intent Routing Workaround from Capabilities 16 & 17

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This document is self-contained.** It assumes no prior conversation. Everything you need — repo, branch, file paths, the exact defect shapes, the traps, and the verification commands — is below.

**Goal:** Make two Harbor eval tasks (`agent-code-execution-v1`, `agent-external-databases-v1`) exercise **real production intent routing** instead of a harness workaround that fakes it, so their eventual recorded runs measure the product rather than the scaffolding.

**Architecture:** Each task has an *adapter* (`environment/run_agent.py`) that drives the LangGraph agent and emits evidence, and a *verifier* (`tests/verify.py`) that gates that evidence. Today the adapter injects a fake intent and the verifier **asserts that it did**. This plan inverts that: the adapter drives a real turn, and the verifier proves routing was genuine.

**Tech Stack:** Python 3.11/3.12, Harbor 0.6.6, LangGraph, Docker Compose doubles, pytest-free plain-script verifiers.

---

## Background — read this before touching anything

**The repo:** `Goodwiinz/rag`. Base branch `develop`.

**Why the workaround exists.** Three agent tools were dead in production — registered but bound to no intent and no subgraph, so the graph could never route to them:

```
execute_code               intents=∅  subgraphs=∅
search_external_database   intents=∅  subgraphs=∅
list_external_databases    intents=∅  subgraphs=∅
```

The eval tasks were authored against that broken state. To exercise the tools anyway, each adapter seeds the checkpoint as if `preprocessing_node` had already classified the turn:

```python
await graph.aupdate_state(config, seed_state, as_node="preprocessing_node")
```

with a **sentinel** (non-`AgentIntent`) value, which makes `route_by_intent` fall through to the general path where `_get_tools_for_intent` binds `ALL_TOOLS`.

**Why it can go now.** PR #1378 landed the real bindings on `develop`. Verify before starting (`git show origin/develop:backend/src/services/agent/tools.py`):

| Tool | `intents` | `subgraphs` |
| --- | --- | --- |
| `execute_code` | `{RESEARCH}` | `{RESEARCH}` position 9 |
| `search_external_database` | `{GENERAL}` | ∅ |
| `list_external_databases` | `{GENERAL}` | ∅ |

**If any of those still show `frozenset()`, STOP** — #1378 has been reverted or you are on the wrong base. Do not proceed.

**Reference implementation.** The same surgery was already done for a third task, `agent-memory-roundtrip-v1`, in PR **#1380** (branch `feat/drop-sentinel-memory`). If that PR has merged, read it on develop; if not, read the branch. It is the model to follow — particularly its `check_real_routing` and `check_turn3_sent` gates. Note one difference: that task never had a `check_sentinel_routing` gate or a `sentinel_intent` truth field, so it *added* a gate. **Both tasks in this plan DO have them, so you are inverting an existing gate, not adding one.**

---

## Global Constraints

- **`evals/harbor_common/` is READ-ONLY.** Consume: `envelope.run_verifier_main(benchmark_id, gate_fn)` / `envelope.InfrastructureFailure` / `envelope.load_inputs`, `db.*`, `network.validate_network_boundary`, `trajectory.*`, `serialization.*`. Changing the kernel invalidates every task digest in the repo — if you think you need to, STOP and escalate.
- **Never modify these digest-pinned task dirs:** `evals/agent-direct-project-action-v1`, `evals/agent-stream-cancel-durability-v1`, `evals/rag-retrieval-safety-grounding-v1`.
- **Verifier exit protocol:** `0` pass, `10` gate failure, `2` infrastructure failure. Missing evidence keys, absent services, or empty result sets must raise `InfrastructureFailure` — never silently pass. "Nothing happened" must never read as "it worked."
- **Any byte change inside a task dir moves its digest.** Recompute and update the matching file in `evals/source-manifests/`. Confirm the recipe by first reproducing a known-good existing manifest value before trusting it:
  ```
  find evals/<task> -type f -not -path "*__pycache__*" | sort | xargs shasum -a 256 | sort -k2 | shasum -a 256
  ```
- **The backend lint gate is BLOCKING in CI and it covers `evals/`.** Run `ruff check`, `black --check`, `isort --check-only` on every changed Python file before handing off. This exact gate has broken four PRs in this workstream. `mypy` skips `evals/` and only blocks *added* files.
- **Shell trap that will lie to you:** when running calibration fixtures, capture `$?` into a variable **before** any command substitution. `$(basename …)` resets `$?`, so `echo "$(basename $f) -> $?"` reports `0` for everything and makes a broken verifier look perfect.
  ```bash
  for f in evals/<task>/tests/calibration/*.json; do
    BENCHMARK_CALIBRATION_FIXTURE=$f VERIFIER_REPORT_PATH=/tmp/v.json python evals/<task>/tests/verify.py >/dev/null 2>&1
    rc=$?; n=$(basename "$f"); echo "$n -> $rc"
  done
  ```
  Both env vars are required: without `VERIFIER_REPORT_PATH` the verifier tries to write `/logs/verifier/audit.json`.
- **Tasks ship NOT GATED.** Gating requires a 5-trial recorded run with zero infrastructure failures, which is out of scope here and needs credentials this environment does not have.
- **Verification here is calibration-only, never run-verified.** There is no Docker or Azure in the authoring environment, so the task cannot execute end to end. Say that plainly in the report and PR body; do not let "verified" imply the benchmark ran.
- **Work in a git worktree off `origin/develop`.** Do not edit a shared checkout that may sit on another branch; read canonical file contents with `git show origin/develop:<path>`.
- **One PR for both tasks** — they are the same change twice and share a reviewer's context.

---

## THE TRAP — read this twice, it is the whole difficulty

Removing the sentinel means the turn's **real classification** must route to a subgraph/intent where the tool is actually bound. The two tasks need **opposite** classifications, and getting it wrong means the tool is never reached and the task fails every live run.

### How routing actually works

- `route_by_intent` sends `research` / `writing` / `knowledge_graph` intents **straight to their subgraphs**. Inside a subgraph, tools bind by **subgraph membership** (`descriptors_for_subgraph`) — the `intents` field is not consulted.
- Only the **general** path's `llm_node` consults `intents`, via `_get_tools_for_intent`.

Therefore:

| Task | Tool | Bound how | Turn MUST classify as |
| --- | --- | --- | --- |
| `agent-code-execution-v1` | `execute_code` | RESEARCH **subgraph** | **`research`** |
| `agent-external-databases-v1` | both connectors | `intents={GENERAL}`, no subgraph | **`general`** |

**These are opposite requirements.** A wording that helps one breaks the other.

### How to compute the classification without running anything

The keyword table is `INTENT_KEYWORDS` in `backend/src/services/agent/_prompts.py` (starts ~line 37). Scoring lives in `backend/src/services/agent/classifier.py` (~lines 207-250): word-boundary regex per keyword, summed per intent, `confidence = score / (score + 2)`.

Research keywords include: `search`(2), `find`(2), `look up`(2), `discover`(2), `ingest`(2), `import`(2), `arxiv`(2), `knowledge base`(2), `our docs`(2), `our library`(2), `our documents`(2), `paper`(1), `papers`(1). Read the file for the full current table rather than trusting this excerpt.

Two behaviours that matter:
- Word-boundary matching means a keyword inside an identifier does **not** match: `search_external_database` does not trigger `search`, because `h`→`_` is not a word boundary.
- There is a short-query shortcut around `classifier.py:420`: below a length threshold with zero keyword signal it can skip the LLM. Above it, classification **escalates to the LLM**, which also sees `previous_turn` context. So a zero-score prompt is not a guarantee of `general` on the happy path — it is only a guarantee of the **fallback** verdict when the LLM errors or times out (`classifier.py:503-530`).

### Current instruction text (verify these are still current before relying on them)

`agent-code-execution-v1` (`environment/run_agent.py:59`):
> `Run Python to compute the SHA-256 hex digest of the exact string "<TARGET>" and report the digest.`

Score this yourself. As written it appears to carry **no research keywords**, which would make the keyword fallback `general` — and on the general path `execute_code` (`intents={RESEARCH}`) is **not bound**. **This is the likely failure and the main work of Task 1 below.**

`agent-external-databases-v1` (`environment/run_agent.py:49`):
> `First call list_external_databases to see which external database connectors are available. Then call search_external_database with connector="pubmed" for research on "telomere shortening senescent cells", and call search_external_database with connector="fred" for the economic series "unemployment rate". Report what you found from each source.`

Score this too. `search` appears only inside identifiers (no boundary match) and `research` is **not** a keyword — so it plausibly scores 0 → `general`, which is what this task needs. Confirm rather than assume; `found` / `find` and similar near-misses deserve a careful look.

---

## Task 1: `agent-code-execution-v1` (capability 16)

**Files (all under `evals/agent-code-execution-v1/` unless noted):**
- Modify: `environment/run_agent.py` (3 `aupdate_state` sites), `tests/verify.py` (`check_sentinel_routing` at ~line 146), `tests/truth.json` (drop `sentinel_intent`), `task.toml`
- Add: one calibration fixture under `tests/calibration/`
- Modify: `evals/specs/agent-code-execution-v1/{task.md,environment.md,harness.md}`, `evals/AGENT_FLOW_BASELINE.md` (capability 16 section), `evals/source-manifests/<the manifest covering this task>`

**Existing gate to invert** (`tests/verify.py:146-152`):
```python
def check_sentinel_routing(evidence, failures):
    if (evidence.get("env_flags") or {}).get("routing_workaround") != "sentinel_intent":
        failures.append("env_flags.routing_workaround != 'sentinel_intent'")
    if evidence.get("sentinel_intent") != SENTINEL_INTENT:
        failures.append("sentinel_intent does not match the approved sentinel")
    if evidence.get("observed_intent") != SENTINEL_INTENT:
        ...
```

- [ ] **Step 1: Confirm the premise.** Check the three bindings table above against `git show origin/develop:backend/src/services/agent/tools.py`. Confirm `execute_code` is `subgraphs={RESEARCH}` and `policy_tags` still contains `DESTRUCTIVE`. If not, STOP.

- [ ] **Step 2: Solve the routing problem BEFORE writing code.** Score the current instruction against the real `INTENT_KEYWORDS` table. Decide how the turn will classify as `research` so `execute_code` is bound. Options, in order of preference:
  1. Reword the instruction so it legitimately scores `research` (e.g. it genuinely involves looking something up) — but the reword must stay a truthful description of what the task asks, not keyword-stuffing that misdescribes the work.
  2. Accept LLM classification and document the risk, with the keyword fallback still landing on `research` so a classifier outage doesn't misroute.

  Write your scoring work into the report: each candidate wording, its per-intent score, and the resulting verdict. **Do not skip to code.** If you cannot find a wording that reaches `research` honestly, STOP and escalate — that is a finding about the product's routing, not a thing to paper over.

- [ ] **Step 3: Rewrite the adapter.** Remove all three `aupdate_state` sites and the sentinel seeding; drive a real user turn. Record the **observed** intent by reading `graph.aget_state(config).values["intent"]` — the real checkpoint value, **not** something the adapter asserts about itself. Emit it in evidence. Remove `routing_workaround` from `env_flags`.

- [ ] **Step 4: Invert the verifier gate.** Rename `check_sentinel_routing` → `check_real_routing`. It must now FAIL when: `env_flags` carries `routing_workaround`; the observed intent equals the retired sentinel value; or the observed intent is not a real `AgentIntent` that legitimately binds `execute_code`. Keep the retired sentinel string in the file so the gate can reject it by name. Remove `sentinel_intent` from `tests/truth.json`.

- [ ] **Step 5: Preserve the HITL gate — `execute_code` is DESTRUCTIVE.** The root-graph interrupt must still fire before any sandbox is created, and the pre-approval state snapshot must still prove nothing executed before approval. Losing confirmation while "fixing" routing would be a security regression. Assert it explicitly and state in your report which evidence field proves it.

- [ ] **Step 6: Add the regression fixture.** A calibration fixture carrying the OLD shape (`env_flags.routing_workaround = "sentinel_intent"`, observed intent = the sentinel) must now exit **10**, naming the routing gate. Follow the directory's existing naming convention (`wrong-*` → exit 10, `infra-*` → exit 2). Without this fixture, a regression back to the workaround passes silently.

- [ ] **Step 7: Guard against the "turn never happened" false pass.** Graph state persists across turns, so evidence from a run where the user turn was never actually sent can satisfy a routing gate. Assert the instruction text byte-for-byte against the evidence AND that a matching `human` message exists in the recorded messages. (This exact false pass was caught by review on the reference task — do not re-ship it.) Add a fixture proving it fails.

- [ ] **Step 8: Re-pin and document.** Set `source` / `source_revision` in `task.toml` to a real `develop` commit at or after the #1378 merge (verify with `git cat-file -t <sha>` → must print `commit`). **Leave `base_image_digest` unchanged** — the task Dockerfile uses the registry image only as a dependency base and `COPY backend/` brings the agent code from the build context, so no image rebuild is involved and dependencies did not change. Update the spec trio and the capability-16 section of `AGENT_FLOW_BASELINE.md` to stop describing the workaround as current; keep a short historical note explaining it existed and why it went.

- [ ] **Step 9: Recompute the digest**, update the manifest, run the full calibration matrix (real exit codes, using the `rc=$?` pattern above), run the lint gate, and confirm `git diff --stat origin/develop..HEAD -- evals/harbor_common evals/agent-direct-project-action-v1 evals/agent-stream-cancel-durability-v1 evals/rag-retrieval-safety-grounding-v1` is empty. Report, do not commit.

---

## Task 2: `agent-external-databases-v1` (capability 17)

Same shape, with the routing target **`general`** instead of `research`, and no destructive tool.

**Files:** same layout under `evals/agent-external-databases-v1/`, its spec trio, the capability-17 baseline section, and its manifest. The existing gate is `check_sentinel_routing` at `tests/verify.py:156-162`; `tests/truth.json` carries `sentinel_intent` plus connector-inventory truth (`total_connectors`, `key_gated_connectors`, `pubmed_pmids`, `fred_series_ids`, …) that must be left intact.

- [ ] **Step 1: Confirm the premise** — both connectors `intents={GENERAL}`, `subgraphs=∅`.
- [ ] **Step 2: Score the current instruction** against the real keyword table and confirm it lands on `general`. Watch for near-misses (`find`/`found`, `search` outside identifiers, `discover`). If it scores research, reword minimally and record the before/after scores. If it already scores 0, say so with the evidence and change nothing.
- [ ] **Step 3: Rewrite the adapter** — no `aupdate_state` (2 sites here), observed intent read from real graph state, `routing_workaround` removed from `env_flags`.
- [ ] **Step 4: Invert the gate** to `check_real_routing`, failing on the workaround flag, the retired sentinel, or an intent that does not bind the connectors. Remove `sentinel_intent` from `truth.json`, leaving the connector-inventory truth untouched.
- [ ] **Step 5: Keep the anti-fabrication gates.** This task's whole point is that the agent must not invent connector results; `wrong-fabricated-result.json` already covers that. Do not weaken it while editing around it — re-run it and confirm it still exits 10 for its own reason.
- [ ] **Step 6: Regression fixture** for the old sentinel shape → exit 10.
- [ ] **Step 7: The "turn never happened" guard**, as in Task 1 Step 7, with its own fixture.
- [ ] **Step 8: Re-pin and document** — same rules; `base_image_digest` unchanged.
- [ ] **Step 9: Recompute digest, matrix, lint, pinned-dir check.** Report, do not commit.

---

## Verification

For each task:
1. Full calibration matrix with **real** exit codes: `pass.json` → 0, every `wrong-*` → 10 (each isolated to its own gate — check the emitted failure list, not just the code), every `infra-*` → 2.
2. Task digest recomputed and matching its manifest entry.
3. `ruff check` / `black --check` / `isort --check-only` clean on changed Python.
4. `harbor_common` and the three pinned task dirs untouched.
5. `git cat-file -t` on every SHA written into `task.toml`.

Whole branch, before the PR: a review pass focused on the one question that matters — **can either task now pass without having exercised real routing?** Specifically: is the observed intent read from graph state or self-asserted; does the sentinel fixture fail for the routing reason and not incidentally; and does a fixture with the user turn removed still pass?

## Risks

- **Wrong routing target.** `execute_code` needs `research`, the connectors need `general`. Swapping them means the tool is never bound and the task fails every live run. This is the single most likely way to get this wrong.
- **Losing HITL on `execute_code`.** It is DESTRUCTIVE; the interrupt must still fire before execution. A routing change must not move it onto a path whose subgraph has `has_interrupt=False` (this is exactly why #1378 bound it to RESEARCH and explicitly not DATA — `data_agent.py` sets `has_interrupt=False`).
- **The inverted gate that still passes the old shape.** If the inversion is written incorrectly, the task passes while never exercising real routing — the exact false-pass class this suite exists to catch. The regression fixture in Step 6 is the guard; it is not optional.
- **Keyword-stuffing an instruction** to force a classification makes the benchmark measure a phrasing trick rather than the product. If honest wording cannot reach the required intent, that is a real finding about routing — escalate instead of hiding it.
- These tasks remain **calibration-verified only**; a recorded run is still required before either can be gated.
