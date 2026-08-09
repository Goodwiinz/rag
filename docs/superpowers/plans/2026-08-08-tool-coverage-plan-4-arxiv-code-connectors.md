# Tool-Coverage Benchmark Plan 4: arxiv-research-flow + code-execution + external-databases

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Ship the last three tasks of the tool-coverage benchmark — `agent-arxiv-research-flow-v1` (capability 5: `search_arxiv` + `ingest_arxiv_papers` against an arXiv protocol double, with Redis-cache and local-object-storage assertions), `agent-code-execution-v1` (new capability: `execute_code` against an E2B wire double), and `agent-external-databases-v1` (new capability: `search_external_database` + `list_external_databases` against a connector double) — calibration-verified and recorded. All three are **`semantic = N/A`** (design doc §Layer B): no judge anywhere in this plan.

**Architecture:** Task 1 is a hybrid of the two established patterns — graph-level adapter (`agent-direct-project-action-v1`: `compile_agent_graph` + `astream` + HITL resume, since `ingest_arxiv_papers` is DESTRUCTIVE) **plus** a mock-services protocol double (`rag-retrieval-safety-grounding-v1` `server.py` pattern: request-event recorder) serving arXiv Atom XML and deterministic PDF bytes, **plus** the redis-in-compose pattern from `agent-stream-cancel-durability-v1` (redis:7.4-alpine service, verifier reads via `redis.Redis.from_url`). Tasks 2 and 3 are protocol-double tasks whose tools are **unreachable via live intent classification on the pinned image** (see Routing reality below) — both use the **sentinel-intent `aupdate_state` workaround** (plan-3 memory-task precedent) to route the turn onto the general path's `ALL_TOOLS` binding, honestly recorded as an `env_flags` comparison identity.

**Tech Stack:** Python 3.11, psycopg 3, redis-py, LangGraph agent graph from pinned backend image (`registry.digitalocean.com/ragsystemregistry/backend:3a436b2-r1`, digest `sha256:75b224f8…c0e34`), `e2b-code-interpreter==2.7.0` (in the pinned image via `backend/requirements.txt:132`), Harbor 0.6.6 task schema 1.2, docker-compose + Squid egress proxy.

**Model roles:** Fable plans/reviews (this doc); **Sonnet** implements each task; **Opus** runs spec + quality review between tasks; **Fable** whole-branch final verify before PR.

## Dependency / stacking

This branch (`feat/tool-coverage-bench-plan4`) is cut **off develop** and already carries `evals/harbor_common/` plus all merged plan-1/plan-2 tasks. Plan 3 (`feat/tool-coverage-bench-plan3`, PR #1362) is **in flight and NOT on this branch** — no code dependency exists (plan-4 needs no judge and nothing plan-3 adds), but plan-3 **claims UUID blocks `08xx`/`09xx` and the baseline capability sections 7 + 9**. Plan 4 therefore takes `10xx`/`11xx`/`12xx` and touches only its own baseline sections; expect a trivial `AGENT_FLOW_BASELINE.md`/`README.md` merge conflict with #1362 — resolve by keeping both plans' additions, never rewriting the other's rows.

## Global Constraints

- Design doc `docs/superpowers/specs/2026-08-07-tool-coverage-benchmark-design.md` is **binding** — task 1 = capability 5, tasks 7/8 = new capabilities; scoring Layers A/C (Layer B = N/A for all three, counts as pass); trials 3 canonical + 2 near-boundary. **One design-doc assumption is corrected by recon** (see Routing reality): the "unknown-intent `ALL_TOOLS` path" the doc relies on for tasks 7/8 is never taken via live classification — the sentinel-intent workaround replaces it, documented per task.
- `harbor_common/` is consumed, never forked. Available on this branch: `envelope.{load_inputs,run_verifier_main,InfrastructureFailure}` (unified `{"evidence":…,"state":…}` calibration envelope; exit 0/10/2), `db.{bootstrap_schema,seed_tenant,initial_agent_state}`, `network.validate_network_boundary(model_endpoint, extra_probes=…)`, `judge.run_semantic_judge` (NOT used here), `serialization.{json_safe,utc_now}`, `trajectory.build_atif_trajectory`, `templates/{test.sh,proxy/}`. There is **no harbor_common redis helper** — the arXiv task rolls its own verifier-side redis read, exactly like `agent-stream-cancel-durability-v1/tests/verify.py:139-143` (`redis.Redis.from_url(REDIS_URL, decode_responses=True)`).
- All previously landed tasks (3 originals + `agent-project-management-v1` + `agent-writing-flow-v1` + `agent-kb-retrieval-v1`) are **digest-pinned — do not touch**.
- Spec files `evals/specs/<task>/{task.md,environment.md,harness.md}`: line 1 `Status: approved`, `Label:` paragraphs, no markdown headings. Task 1 matches `agent-direct-project-action-v1` label order; tasks 2/3 match `rag-retrieval-safety-grounding-v1` label order (has Data / Storage and reset / Fidelity limits — both need a Fidelity-limits paragraph for their monkeypatch/env seams).
- Reward protocol: verify.py exit `0` → reward 1, `10` → reward 0, anything else → infra, no reward file.
- Fixed UUID blocks (format `00000000-0000-4000-8000-000000001001` etc.): **`10xx`** = arxiv, **`11xx`** = code-execution, **`12xx`** = external-databases. Highest in use on this branch is `…0706`; `08xx`/`09xx` are reserved by plan 3 (#1362). Nothing anywhere uses `10xx`+ (verified by grep).
- `EXPECTED_INSTRUCTION` triple-declared byte-identical (instruction.md, environment/run_agent.py, tests/verify.py). No `test_`-prefixed files in task dirs except `test.sh`.
- **Impl caps are ground truth, not wrapper caps:**
  - `search_arxiv`: wrapper clamps to 50 (`tools.py:226`) but impl hard-caps `min(max_results, 5)` + 250-char abstracts (`tools_impl.py:1027`) — assert ≤5 results.
  - `ingest_arxiv_papers`: wrapper **silently truncates** to 10 (`paper_ids[:_MAX_INGEST_BATCH]`, `tools.py:261`); the impl's `>10 → error "Maximum 10 papers per ingest request"` (`tools_impl.py:1174-1175`) is **dead code through the agent wrapper**. The near-boundary trial asserts truncation, not rejection (Landmine 4).
  - `execute_code`: `MAX_EXECUTIONS_PER_RUN = 5`, `MAX_EXECUTION_TIMEOUT = 300` (`e2b_sandbox_manager.py:53-56`).
  - `search_external_database`: wrapper clamps to 100 (`tools.py:754`) but impl caps `min(max_results, 20)` (`tools_impl.py:2997`); connector/domain names sanitized by `_validate_connector_name` (`tools.py:98`).
  - Research subgraph loop ceiling: `MAX_RESEARCH_TOOL_LOOPS = 5` (`research_agent.py:41`).
- Commits small, one per task, conventional format.

## Routing reality (READ FIRST — corrects both the design doc and the plan-4 briefing)

Verified on this branch against `tools.py` / `_nodes_llm.py` / `_nodes_classify.py` / `classifier.py`:

| tool | intents | subgraphs | policy_tags | reachable via live classification? |
|---|---|---|---|---|
| `search_arxiv` | RESEARCH, GENERAL | RESEARCH@0, WRITING@5 | SLOW, NO_OUTER_RETRY, CONTEXT_FREE | **yes** (research route) — `tools.py:863-878` |
| `ingest_arxiv_papers` | RESEARCH, GENERAL | RESEARCH@1, WRITING@6 | **DESTRUCTIVE**, SLOW, NO_OUTER_RETRY | **yes** (research route) — `tools.py:879-895` |
| `execute_code` | RESEARCH, KNOWLEDGE_GRAPH | **∅** | **DESTRUCTIVE** | **NO** — `tools.py:1076-1082` |
| `search_external_database` | **∅** | **∅** | CONTEXT_FREE | **NO** — `tools.py:1083-1089` |
| `list_external_databases` | **∅** | **∅** | CONTEXT_FREE | **NO** — `tools.py:1090-1096` |

Why the three "NO"s, mechanically: `route_by_intent` (`_nodes_classify.py:239-248`) sends research/writing/knowledge_graph to subgraphs which bind **only** `descriptors_for_subgraph(...)` (`research_agent.py:31-33`, `tool_registry.py:213-218`) — a tool with `subgraphs=∅` is never bound there. The general path's `llm_node` binds `_get_tools_for_intent(state.intent)` (`_nodes_llm.py:122-127`), which returns `ALL_TOOLS` **only for an intent outside `AgentIntent`** — and the classifier is Literal-typed to exactly the four valid intents (`classifier.py:35,74`), so that branch is dead in production. For intent `general` it binds `descriptors_for_intent("general")`, which includes none of the three.

**Consequence 1 (corrects the briefing):** `execute_code` is NOT reachable via research/kg intent. Its `intents={RESEARCH, KNOWLEDGE_GRAPH}` entries are dead metadata under subgraph routing — research/kg turns run in subgraphs that bind by *subgraph*, and `execute_code` has `subgraphs=∅`. It is in the same dead-tool boat as the connectors (and `forget_memory`).

**Consequence 2 — the reach decision (option b, sentinel intent):** Tasks 2 AND 3 both use the **`aupdate_state` sentinel-intent workaround** (plan-3 memory-task precedent): the adapter seeds the user message + a sentinel `intent` (e.g. `"benchmark_all_tools"`, any non-`AgentIntent` string) via `graph.aupdate_state(config, {...}, as_node="preprocessing_node")` so `route_by_intent` falls through to the general path and `_get_tools_for_intent(sentinel)` returns `ALL_TOOLS` (`_nodes_llm.py:125-126`) — which includes all three tools (`exposed_in_all_tools` defaults True; only `do_kb_retrieve`/`load_project_skill` opt out). **Option (a) — depending on a connectors-reachable routing fix (the forget_memory→GENERAL-style PR) — is rejected for a decisive reason:** the benchmark executes the **digest-pinned image** `3a436b2-r1`; a routing fix merged to develop does not exist inside that image, so (a) cannot work without re-pinning the entire suite, and it additionally blocks this plan on an unmerged production PR. The workaround is recorded per task as `env_flags.routing_workaround = "sentinel_intent"` (comparison identity), Layer A asserts the observed sentinel `intent` in evidence, and each task's baseline **Coverage note** states plainly: *these tools are live-unreachable dead tools in production routing — a product gap tracked separately; when the routing fix lands and the suite re-pins to an image containing it, switch the task to live classification and re-record.* Do NOT edit `backend/src` to make them reachable — that is a production change dressed as a benchmark.

**Consequence 3:** Task 1 is routing-clean — both arXiv tools are RESEARCH-bound, a research-classified turn reaches them, and `ingest_arxiv_papers` fires the research subgraph's HITL interrupt (`RESEARCH_DESTRUCTIVE_TOOLS`, `research_agent.py:125-131`). On the sentinel/general path, `execute_code`'s DESTRUCTIVE tag fires the root-graph `interrupt_node` — Task 2 handles ONE HITL approval.

## Landmines (each verified in code; read before building)

1. **Connector/execute_code dead-tool routing** — the headline risk, resolved above (sentinel intent, option b). The spike in Task 2 Step 1 must demonstrate the mechanics end-to-end before any task files are written.
2. **E2B double feasibility** — the most speculative double (design-doc risk 1). Recon found a clean seam: e2b SDK 2.7.0's `ConnectionConfig` reads **`E2B_API_URL`** and **`E2B_SANDBOX_URL`** from env (verified against the installed SDK), plus `E2B_API_KEY` and `E2B_VALIDATE_API_KEY=false`. No monkeypatch needed. The wire protocol to reproduce: sandbox create (`POST /sandboxes`), the code-interpreter envd execute route used by `AsyncSandbox.run_code` (streamed JSON events), kill (`DELETE /sandboxes/{id}`) — exact paths/shapes captured in the Task 2 spike. **Fallback is binding (design doc): if the double proves infeasible, the task env-gates to `infra-degraded` (verifier exit 2, no reward file) — NEVER a fake pass.** Note `_tool_execute_code` already env-gates honestly: no `E2B_API_KEY` → `{"error": "Code execution is not available…"}` (`tools_impl.py:2938-2939`).
3. **`ingest_arxiv_papers` is DESTRUCTIVE → HITL** (`tools.py:890`): the adapter resumes with `Command(resume={"confirmed": True})`; Layer A asserts interrupt → pre-approval DB snapshot (zero document rows) → approval → rows exist. **Post-ingest references must use the returned `document_ids` (UUIDs), NOT arXiv paper IDs** (CLAUDE.md gotcha; the result carries both — `tools_impl.py:1530-1542`).
4. **The >10 batch cap is a silent wrapper truncation, not a rejection** (`tools.py:259-261` caps `[:10]` *before* the impl's `len>10` check at `tools_impl.py:1174` can fire). Near-boundary trial: instruct 11 IDs → assert the executed tool call carried exactly 10 and the result's `requested_count == 10` — asserting an error message here would be asserting dead code.
5. **arXiv base URLs are hard-coded class constants, not env** — `ARXIV_API_BASE = "https://export.arxiv.org/api/query"`, `ARXIV_PDF_BASE = "https://arxiv.org/pdf"` (`arxiv_service.py:211-212`). The adapter must set the class attributes to the mock host (`ArXivIngestionService.ARXIV_API_BASE = "http://mock-services:8080/api/query"`, `…PDF_BASE = "http://mock-services:8080/pdf"`) before driving the graph; document this seam in `harness.md` Fidelity limits. The mock must answer **both** free-text queries and the ingest path's per-paper metadata lookups (`search_papers(query=f"id:{pid}")` — `tools_impl.py:1205-1208`) with valid Atom XML, plus `GET /pdf/<id>.pdf` with deterministic PDF bytes. Because the double answers instantly, the frontend `postWithLongTimeout` gotcha (5-min arXiv budget) cannot trip — but do NOT "fix" latency by adding delays to the mock.
6. **Redis is load-bearing in Task 1, twice.** (a) L2 search cache: key `arxiv:search:<sha1>` (`_ARXIV_CACHE_REDIS_PREFIX`, `tools_impl.py:800`), value `{"payload":…, "cached_at":…}`, **TTL = `_ARXIV_CACHE_STALE_TTL` = 1800 s** (`tools_impl.py:798`, set at `:998-1003`); fresh window 600 s. Verifier asserts key exists, `0 < TTL(key) <= 1800`, and the second identical search returned `cached: true` with **no second mock query event**. (b) The arXiv service's Redis Lua rate gate (`arxiv:rategate`, min 3 s between requests — `arxiv_service.py:47-48`) is live once REDIS_URL is set: budget ~3 s per arXiv API call in agent-timeout math; do not misread the pacing as a hang.
7. **Calibration runs no-Docker** — unified `{"evidence":…,"state":…}` envelope via `BENCHMARK_CALIBRATION_FIXTURE` + `VERIFIER_REPORT_PATH`; fixtures must carry every state the verifier reads (Task 1: db + redis + mock events + storage listing; Task 2: mock events; Task 3: mock events). Same discipline as plans 1-3: `pass.json → 0`, `wrong-*.json → 10` naming the intended gate.
8. **Connector base URLs are also hard-coded module constants** (`pubmed.py:22-24` — note `_ESEARCH`/`_EFETCH` are f-string-baked at import, patch them directly, not `_BASE_URL`; `fred.py:21` `_BASE_URL` is read at call time). Adapter monkeypatches them to the mock host; `harness.md` Fidelity limits records it. **Availability truth (from `base.py:109-116` + registry):** 11 registered connectors; only `fred` (`FRED_API_KEY`), `alpha_vantage`, `cosmic` have `requires_api_key=True`. With `FRED_API_KEY=<benchmark-token>` set and the other two unset: `fred` available, `alpha_vantage`+`cosmic` **listed-but-unavailable**, the remaining 8 (incl. keyless `pubmed`) available-but-undoubled — so the instruction must target `connector=` explicitly to avoid an un-doubled fan-out (`list_available()` fan-out is the no-connector default, `tools_impl.py:3026`).

---

### Task 0: Branch — DONE

Worktree `/Users/goodwiinz/development/rag-wt-plan4`, branch `feat/tool-coverage-bench-plan4` off develop. Backend venv `/Users/goodwiinz/development/RAG_system/backend/.venv/bin` for any local checks.

---

### Task 1: `agent-arxiv-research-flow-v1` (capability 5)

**Files (new dir `evals/agent-arxiv-research-flow-v1/`):**
- `environment/{Dockerfile, docker-compose.yaml, run_agent.py, proxy/{Dockerfile,entrypoint.sh}, mock_services/{Dockerfile, server.py, fixtures/}}`
- `instruction.md`, `task.toml`, `.gitignore`
- `tests/{verify.py, test.sh, truth.json, calibration/{pass.json, wrong-<mode>.json}}`
- `evals/specs/agent-arxiv-research-flow-v1/{task.md, environment.md, harness.md}`

**UUID block `10xx`:** ORG `…001001`, USER `…001002`, WORKSPACE `…001003`, PROJECT `…001004`, THREAD `…001005`. Fixture arXiv IDs are plain arXiv-shaped strings (e.g. `2401.10001`, `2401.10002`) recorded in `truth.json`.

**Flow under test:** a research-routed turn (live classification — no workaround here) that (a) `search_arxiv` for a fixture topic, (b) `ingest_arxiv_papers` for 2 of the returned IDs into the seeded project (DESTRUCTIVE → **one HITL interrupt + approval**), (c) reports the resulting **document UUIDs**. A second identical `search_arxiv` inside the same run (or a scripted second turn) proves the cache path.

- [ ] **Step 1 — mock-services (arXiv double):** clone the rag `server.py` skeleton (`GET /events` tamper-proof request recorder). Endpoints: `GET /api/query` — parse `search_query`; if it contains `id:<pid>` return the single-paper Atom XML entry, else return the fixture result list as Atom XML (namespace `http://arxiv.org/schemas/atom`, fields the parser reads: id/title/authors/summary/published/categories/links incl. pdf link pointing back at the mock); `GET /pdf/<id>.pdf` — deterministic small PDF bytes (fixed byte string checked into `fixtures/`, stable sha256 recorded in `truth.json`). Every request appended as an event (`{"type": "query"|"pdf", "params"/"path": …}`).
- [ ] **Step 2 — compose:** two-network topology + Squid from `harbor_common/templates/proxy/`; add `mock-services` AND `redis:7.4-alpine` (clone the stream-cancel service stanza incl. healthcheck `redis-cli ping`, `--save "" --appendonly no`) on `benchmark-internal`; main env `REDIS_URL=redis://redis:6379/0`, `STORAGE_BACKEND=local`, `UPLOAD_DIR=/benchmark/uploads`, `NO_PROXY=postgres,redis,mock-services,egress-proxy,localhost,127.0.0.1`, `DO_KB_ENABLED=false` (keeps the ingest dual-write branch off — `tools_impl.py:1374-1377`).
- [ ] **Step 3 — adapter `run_agent.py`:** consume `harbor_common` (bootstrap_schema, seed_tenant, initial_agent_state, validate_network_boundary with `extra_probes` for mock-services + redis internal reachability, build_atif_trajectory, json_safe). **Set `ArXivIngestionService.ARXIV_API_BASE/_PDF_BASE` to the mock host before compiling the graph** (Landmine 5). Drive `compile_agent_graph` + `astream(stream_mode="updates")`; on the `ingest_arxiv_papers` interrupt, snapshot documents count via psycopg (pre-approval), then `Command(resume={"confirmed": True})`. Record milestones: `search_arxiv` execution(s) + results, `interrupt:ingest_arxiv_papers`, `preapproval_db_read`, `approval:ingest_arxiv_papers`, ingest result (full dict — `status`, `document_ids`, `ingested_count`, `failed_papers`, `project_id`), `postapproval_db_read`, mock `/events` dump, redis dump (`arxiv:search:*` keys with TTL + values), storage listing under `UPLOAD_DIR`, `final_assistant_message`.
- [ ] **Step 4 — Layer A verifier `verify.py`** via `run_verifier_main`:
  - identity triple + network-boundary triple (+ private probes: mock + redis internal-only).
  - `search_arxiv` executed; results ≤5 (impl cap); result papers ⊆ fixture set.
  - **HITL ordering:** interrupt → pre-approval snapshot shows **zero** ingested document rows → approval → post-approval rows exist (no-mutation-before-approval gate).
  - independent psycopg read: `documents` rows for ORG `…001001` with `processing_status='COMPLETED'`, `checksum_sha256` == fixture PDF sha256, non-NULL `search_vector` path exercised; project link row present (`project_id` in result == `…001004`); **result `document_ids` are valid UUIDs ≠ arXiv IDs** (Landmine 3).
  - **storage:** file exists at `UPLOAD_DIR/documents/<org>/<doc_id>/<filename>` with bytes matching `checksum_sha256` (`storage.py:69-77` layout).
  - **redis:** `arxiv:search:*` key present, `0 < TTL <= 1800`, payload envelope `{"payload":…, "cached_at":…}`; second identical search evidence shows `cached: true` and the mock `/events` contains exactly ONE non-`id:` query event (Landmine 6).
  - mock events: every `pdf` fetch is for a requested fixture ID; no unexpected hosts.
- [ ] **Step 5 — calibration + trials:** `pass.json` → 0. `wrong-ingest-before-approval.json` → 10 (pre-approval snapshot shows rows — the HITL gate). Near-boundary trials: (i) **11-ID batch** → executed call carries exactly 10 IDs, `requested_count == 10` (Landmine 4 — truncation, not error); (ii) **invalid `project_id`** (non-UUID) → `error_type: "invalid_project_id"` (`tools_impl.py:1180-1189`) classified via `TOOL_ERROR_HINTS`, agent recovers (calls `list_projects` or omits) — assert the error surfaced, not a fake success. Empty-search honesty: fixture query with no matches → payload `warning` "No arXiv papers matched…" (`tools_impl.py:1103-1110`) and the final message says so.
- [ ] **Step 6 — specs triple** (`agent-direct-project-action-v1` label order; environment.md documents the double + redis; harness.md Fidelity limits: class-attr URL seam, instant-mock latency, rate-gate presence).
- [ ] **Step 7 — task.toml:** schema 1.2, benchmark_id, base_image_digest, `[verifier.env]` **empty** (no judge), `[environment.env]` = the six Azure passthroughs + `REDIS_URL` + storage vars, timeouts (verifier 120, agent 360, build 1800), `allow_internet = true` + standard rationale.
- [ ] **Step 8 — commit** `feat(evals): agent-arxiv-research-flow-v1 (capability 5)`.

---

### Task 2: `agent-code-execution-v1` (new capability)

**Files:** same shape as Task 1 (`evals/agent-code-execution-v1/`), `environment/mock_services/` = the E2B double. No redis.

**UUID block `11xx`:** ORG `…001101`, USER `…001102`, WORKSPACE `…001103`, THREAD `…001104`.

**Flow under test:** a sentinel-intent turn asking the agent to compute something only executable code answers deterministically (e.g. "run Python to compute the SHA-256 of the exact string `nous-benchmark-1101` and report the hex digest") — `execute_code` (DESTRUCTIVE → **one root-graph HITL approval**), then the final message must contain the digest **from the sandbox stdout**, which the verifier recomputes independently.

- [ ] **Step 1 — SPIKE (blocking, before any task file): E2B wire double.** Against the installed `e2b-code-interpreter==2.7.0` + `e2b` SDK in the backend venv, stand up a scratch aiohttp server and capture exactly what `AsyncSandbox.create(timeout=…)` + `sandbox.run_code(code)` + `sandbox.kill()` send when `E2B_API_URL`/`E2B_SANDBOX_URL` point at it (`E2B_API_KEY=benchmark-token`, `E2B_VALIDATE_API_KEY=false`). Expected surface: `POST /sandboxes` (create → sandbox_id JSON), the code-interpreter execute route with streamed JSON events (stdout/result/error/end), `DELETE /sandboxes/{id}`. Record the captured request/response shapes into `mock_services/fixtures/` as the double's contract. **The double genuinely executes the submitted Python in a `subprocess.run(..., timeout=…)` inside the mock container** (real stdout, deterministic for deterministic code) and records every request as an event. **If the SDK protocol cannot be reproduced faithfully (streaming envelope, auth handshake, protocol version pinning), STOP: implement the env-gate instead** — task.toml leaves the E2B env unset, `verify.py` detects the flag and exits 2 (`infra-degraded`, no reward file), and the baseline section records the task as env-gated with the spike findings. Never fake-pass (Landmine 2).
  - Also confirm in the spike that the sentinel-intent turn (Step 2 mechanics) binds `execute_code` and that the DESTRUCTIVE tag fires `interrupt_node` on the general path.
- [ ] **Step 2 — adapter:** seed tenant; **sentinel-intent injection**: `aupdate_state(config, {"messages":[user_msg], "intent": "benchmark_all_tools", …}, as_node="preprocessing_node")`, then stream with input `None` so `route_by_intent` evaluates the sentinel → general path → `ALL_TOOLS` (Routing reality, Consequence 2). Resume the `execute_code` interrupt with `Command(resume={"confirmed": True})`. Record: observed `intent` (must equal the sentinel), `interrupt:execute_code`, `approval:execute_code`, tool result (`status/stdout/stderr/exit_code/execution_time_ms`), mock events (create/execute/kill), `final_assistant_message`. `env_flags.routing_workaround = "sentinel_intent"`.
- [ ] **Step 3 — Layer A verifier:** identity + network triples (+ mock internal-only probe); sentinel intent asserted in evidence; HITL ordering with a pre-approval mock-event snapshot proving **no execute request reached the double before approval**; exactly one sandbox created; executed code event present; tool result `exit_code == 0`, `stdout` contains the digest; **verifier recomputes `sha256("nous-benchmark-1101")` and asserts both the stdout and the final message contain it** (grounding without a judge — semantic N/A); executions ≤ `MAX_EXECUTIONS_PER_RUN` (5).
- [ ] **Step 4 — calibration + trials:** `pass.json` → 0; `wrong-execute-before-approval.json` → 10 (HITL gate) — or `wrong-fabricated-stdout.json` → 10 (final message digest ≠ recomputed digest). Near-boundary: (i) **timeout** — instruct a computation the double's subprocess timeout kills → tool result `error: "timeout"`/exit 124 path (`e2b_sandbox_manager.py:163-171`) classified via `TOOL_ERROR_HINTS`, final message reports the failure honestly; (ii) E2B env unset → tool returns `"Code execution is not available…"` and the agent says so (the honest env-gate, also the fallback posture). Both fixtures run no-Docker.
- [ ] **Step 5 — specs triple** (rag label order; Fidelity limits: `E2B_API_URL`/`E2B_SANDBOX_URL` env seam, subprocess-not-firecracker execution, single-language python). **Step 6 — task.toml:** `[environment.env]` = Azure six + `E2B_API_KEY=benchmark-token`, `E2B_VALIDATE_API_KEY=false`, `E2B_API_URL`/`E2B_SANDBOX_URL` → mock host; `[verifier.env]` empty. **Step 7 — commit** `feat(evals): agent-code-execution-v1 (code-execution capability)`.

---

### Task 3: `agent-external-databases-v1` (new capability)

**Files:** same shape (`evals/agent-external-databases-v1/`), `environment/mock_services/` = connector double. No redis.

**UUID block `12xx`:** ORG `…001201`, USER `…001202`, WORKSPACE `…001203`, THREAD `…001204`.

**Flow under test:** a sentinel-intent turn (same mechanics as Task 2) that (a) `list_external_databases` to discover connectors, (b) `search_external_database(connector="pubmed", …)` for a fixture topic, (c) `search_external_database(connector="fred", …)` for a fixture series — final message grounded in the doubled results.

- [ ] **Step 1 — mock-services (connector double):** rag `server.py` pattern + `/events`. PubMed shape: `GET /entrez/eutils/esearch.fcgi` (JSON `esearchresult.idlist`) + `GET /entrez/eutils/efetch.fcgi` (article XML) — mirror what `pubmed.py:118+` actually parses (read it at build time, fidelity to the parser, not to NCBI). FRED shape: `GET /fred/series/search` (JSON `seriess`) per `fred.py:87-152`; the mock **asserts and records the `api_key` query param** (= the benchmark `FRED_API_KEY`). Fixture corpora deterministic, in `fixtures/`.
- [ ] **Step 2 — adapter:** seed tenant; sentinel-intent injection (identical mechanics + `env_flags.routing_workaround`); **monkeypatch `pubmed._ESEARCH`/`pubmed._EFETCH` and `fred._BASE_URL`** to the mock host before compiling (Landmine 8 — `_ESEARCH`/`_EFETCH` are baked at import, patching `_BASE_URL` alone does nothing for PubMed). No HITL (both tools CONTEXT_FREE, non-destructive). Record tool executions + results, mock events, final message.
- [ ] **Step 3 — Layer A verifier:** identity + network triples (+ mock internal-only probe); sentinel intent asserted; `list_external_databases` result: `total == 11`, `fred.available == true`, `alpha_vantage`/`cosmic` `available == false` with `requires_api_key == true` (Landmine 8 truth table — the design doc's "9 unavailable" is corrected by recon: only key-gated connectors read unavailable); both searches executed with `connector` explicit and `max_results ≤ 20` (impl cap); result rows ⊆ fixtures (ids/titles match; `content` truncated to 300 chars per `tools_impl.py:3052`); FRED event carries the benchmark api_key; `connectors_searched` == exactly the targeted connector per call; final message's claims appear in the doubled results (deterministic containment check — semantic N/A).
- [ ] **Step 4 — calibration + trials:** `pass.json` → 0; `wrong-fabricated-result.json` → 10 (final message cites a paper/series not in the fixtures) — or `wrong-unknown-host.json` → 10 (an event shows a query the double never served). Near-boundary: (i) **unknown connector name** → `{"error": "Unknown connector: …", "available_connectors": […]}` (`tools_impl.py:3002-3007`) classified + agent recovers by listing; (ii) **unavailable connector** (`connector="alpha_vantage"`) → error naming the missing `api_key_env_var` (`tools_impl.py:3008-3014`), agent reports honestly; (iii) invalid `domain` → `valid_domains` list (`tools_impl.py:3019-3023`). Both fixtures run no-Docker.
- [ ] **Step 5 — specs triple** (rag label order; Fidelity limits: module-constant monkeypatch seam, 2-of-11 connectors doubled, undoubled keyless connectors deliberately not exercised — instruction pins `connector=`). **Step 6 — task.toml:** `[environment.env]` = Azure six + `FRED_API_KEY=<benchmark-token>` + mock hosts; explicitly do NOT set `ALPHA_VANTAGE`/`COSMIC` keys; `[verifier.env]` empty. **Step 7 — commit** `feat(evals): agent-external-databases-v1 (external-databases capability)`.

---

### Task 4: docs, manifest, baseline skeletons

**Files:** modify `evals/AGENT_FLOW_BASELINE.md`, `evals/README.md`; create `evals/source-manifests/agent-flow-2026-08-08-arxiv-code-connectors.json`, `evals/baselines/agent-flow-2026-08-08-arxiv-code-connectors.json`.

- [ ] **Step 1 — baseline:** promote capability 5 from its roadmap paragraph to a full gated-format section (cap-14 structure: `**Preconditions:**` the `10xx` UUIDs; `**Objective gates:**` bullets with file:line anchors — HITL, truncation-not-rejection, redis TTL, storage checksum, document-UUID identity; `**Coverage note:**`; `**Semantic:** N/A (deterministic)`; `**Status:** NOT YET GATED — awaits first recorded run`). Add two NEW capability sections (code-execution, external-databases) in the same format — each with the **routing-workaround Coverage note** (live-unreachable dead tools; sentinel-intent comparison identity; revisit on routing-fix + re-pin) and, for code-execution, the env-gate fallback posture. Do not touch plan-3's rows/sections (merge-conflict rule in Dependency/stacking).
- [ ] **Step 2 — manifest skeleton** per the existing schema (suite `nous-agent-tools-v1`, `recorded_at ""`, harbor 0.6.6, harness block over `harbor_common/**` + `harbor_agents/**` with sha256s, task_digests for the three new tasks via the pinned recipe `find evals/<task> -type f ! -path '*__pycache__*' -exec shasum -a 256 {} + | sort -k2 | shasum -a 256`, invalidation_rule verbatim). Carry plan-2's digest-reproducibility note: compute final digests in the Linux verify container at run time, not from a macOS checkout.
- [ ] **Step 3 — baseline skeleton:** `verifier_calibration` = 3 × `{pass:1, wrong:0}`, `benchmarks: []`, aggregate zeros, "awaits first recorded run".
- [ ] **Step 4 — README** task-table rows + run commands. **Step 5 — commit** `docs(evals): promote capability 5 + add code-execution/external-databases; manifest/baseline skeletons`.

---

### Task 5: calibration verification gate (Opus, no Docker)

- [ ] Each task's `verify.py` via `BENCHMARK_CALIBRATION_FIXTURE` + `VERIFIER_REPORT_PATH`: `pass.json → exit 0`; `wrong-*.json → exit 10` with `failures[]` naming the intended gate.
- [ ] `python evals/harbor_common/selftest.py` → `selftest ok`.
- [ ] Adversarial probes per task: corrupted benchmark_id → 10; Task 1 missing-approval milestone → 10; Task 1 redis TTL absent/oversized in fixture → 10; Task 2 stdout/final-digest mismatch → 10; Task 2 E2B-env-unset fixture → the env-gate path behaves as designed (2 if gated as infra, or the honest-error near-boundary as built); Task 3 fabricated citation → 10.
- [ ] Previously landed task dirs byte-untouched (`git status`); no `backend/src` changes anywhere on the branch.
- [ ] `black --check` / `isort --check-only` on new `.py`; `ruff check evals` clean; `pytest tests/unit -q` smoke (eval-only branch — nothing should move).

---

### Task 6: recorded runs (GATED — Docker + Azure; manual)

Prereqs: Docker up; `doctl registry login`; backend image pulled `--platform linux/amd64`; dev-faithful Azure via Infisical `/do-kb` with `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5.6-luna`. **No judge creds needed — all three tasks are semantic N/A.**

For each task: `harbor run --path evals/<task> --agent-import-path evals.harbor_agents.nous_production_agent:NousProductionAgent --env docker --jobs-dir evals/jobs --job-name <task>-<sha> --force-build --n-concurrent 1 --yes`. On green (objective 5/5, semantic N/A, 0 infra — or, for Task 2 only, the documented env-gate outcome if the spike forced the fallback): populate `benchmarks[]`, `recorded_at`, `repository_revision`, flip capability sections to GATED (or `ENV-GATED (infra-degraded)` for a fallback Task 2), finalize digests in-container. Then open the PR (base develop; if #1362 landed first, rebase and resolve the baseline/README additive conflicts) and enter the merge loop.

**Do NOT patch a verifier or a double to make a run pass.** Red is signal: read `audit.json` `failures[]` + the evidence, fix the task (or accept the env-gate), re-run.

---

## Risks & decisions carried

1. **Sentinel-intent workaround (Tasks 2/3) — decided, option (b).** Option (a) (wait for the connectors-reachable routing fix) is impossible against the digest-pinned image and blocks on an unmerged PR; the workaround is deterministic, precedented (plan-3 memory task), and honestly recorded (`env_flags` + Coverage note). Revisit when the suite re-pins to an image containing the fix.
2. **`execute_code` reachability was over-claimed upstream** — recon shows it is NOT research/kg-reachable (subgraphs=∅; subgraph routing binds by subgraph, not intent). Both the design doc's "unknown-intent path" assumption and the plan-4 briefing's "task 7 has no such issue" are corrected here; Task 2 uses the same workaround as Task 3.
3. **E2B double fidelity (design-doc risk 1)** — spike-first with the `E2B_API_URL`/`E2B_SANDBOX_URL` env seam; binding fallback = env-gate to infra-degraded, never fake-pass.
4. **Ingest batch cap is a silent truncation** — the near-boundary trial must assert truncation; an error-assertion would test dead code and fail forever.
5. **Hard-coded upstream URLs (arXiv, PubMed, FRED)** — adapter-level class-attr/module-constant patches are the only seams; each is declared in `harness.md` Fidelity limits so the fidelity cost is on the record, not hidden.
6. **Rate-gate pacing** — with REDIS_URL set, arXiv API calls space ≥3 s apart; agent-timeout budgets in Task 1 must absorb ~4 gated calls (search + 2 id-lookups + retry headroom).
7. **Plan-3 collision surface** — UUID blocks and baseline sections are disjoint by construction; only `AGENT_FLOW_BASELINE.md`/`README.md` can conflict, additively.

## Execution handoff

Two options — this plan is built for either:
1. **Subagent-Driven (same session)** — fresh Sonnet implementer per task, Opus spec-then-quality review between tasks, Fable whole-branch final verify before PR.
2. **Parallel Session** — new session in the `/Users/goodwiinz/development/rag-wt-plan4` worktree with `superpowers:executing-plans`.

This is the final plan of the tool-coverage train (plans 1-4 cover 22 of 23 registry tools; `load_project_skill` stays deferred per the design doc).
