# Streaming audit v2 (line-level, isolated) — started 2026-08-25
Source: opencode session, partition-once methodology — 4 scope owners + 1 cross-boundary reviewer. Supersedes streaming-audit-2026-08-24.md (tainted provenance); prior IDs S-* re-verdicted below.

## Provenance
- session_id: streaming-line-audit-20260825-054157-57015
- checkout: /Users/goodwiinz/.audit-worktrees/RAG_system/streaming-line-audit-20260825-054157-57015/worktree (read-only, launcher-created)
- ref: origin/develop
- sha: 9685425ca35c791b27c2a6478e0c2f228ec32627
- primary_head_at_launch: b322cf472a583beeab80abd1a9fe0750224c42f3
- dirty_status_at_launch: recorded in session.env; verify receipt post-audit: worktree byte-identical (4245 files), HEAD pinned, primary HEAD + dirty-count unchanged
- launched_at: 2026-08-25T05:41:57Z
- isolation: launch_audit.sh launch --ref develop --slug streaming-line-audit

## Partition (validated, no overlap — 30 files)
sse-backend: streaming.py 149393B/3430ln C, stream_buffer.py 5762B/159ln C, threads/stream.py 8490B/206ln C, stream_service.py 13819B/376ln C
agent-services: run_event_types.py 7933B/237ln C, job_store.py 27182B/651ln C, observability.py 29767B/764ln C, _prompts.py 23710B/462ln C, agent_run_tasks.py 19830B/463ln C, execute.py 53015B/1361ln C
fe-pipeline: agentChatService.ts 28103B/861ln C, useChatStreaming.ts 107041B/2502ln C, agentChatStore.ts 65115B/1570ln C, streamingSlice.ts 5541B/167ln C, agentActivityStore.ts 9040B/269ln C, useSlashCommands.ts 17836B/522ln C(stream-paths), useChatComposerActions.ts 9017B/215ln C(stream-paths)
fe-consumers: AuiMessage.tsx 36145B/1020ln C, ChatRuntimeProvider.tsx 5392B/176ln C, toolUIs.tsx 3452B/109ln C, AuiToolParts.tsx 2678B/88ln C, ArtifactPanel.tsx 13356B/386ln C, useArtifactContent.ts 1128B/35ln C, AgentMessageItem.tsx 11009B/329ln C, AgentMarkdownRenderer.tsx 8554B/291ln C, ToolExecutionCard.tsx 4419B/138ln C, context-rail/AgentActivityPanel.tsx 942B/36ln C, toolLabels.ts 4607B/163ln C, ToolStrip.tsx 4724B/144ln C, markdown-utils.ts 5664B/187ln C
All rows COMPLETE. "Every line audited" claim: VALID for the manifest above.

## Findings
### HIGH
| ID | Finding | Sev | Class | Status |
|----|---------|-----|-------|--------|
| S2-H1 | streaming.py:432 fast-path buffer started WITHOUT run_id → cmid retry of any fast-path turn can never attach: replay polls stream_id_for_run=None 50×0.1s then INTERNAL error while original run live; idempotent retry broken on whole fast-path route (graph route :1467 does it right) | high | confirmed | open |

### MEDIUM
| ID | Finding | Sev | Class | Status |
|----|---------|-----|-------|--------|
| S2-M1 | streaming.py:991-995,:2844 buffer-append failures swallowed bare `except: pass` + confirm/fast-path emitters start buffer without run_id → resumed runs unaddressable, zero observability | med | confirmed | open |
| S2-M2 | streaming.py:1972-1982 + stream_buffer.py:58-76 rag_context bypasses ALL byte bounds (live caps count only; Redis ltrim frame-count only; MAX_PAYLOAD_BYTES only in durable ledger) — same unbounded shape PLAN :1989-1996 / REFLECTION issues[] :2016-2024 | med | confirmed | open |
| S2-M3 | streaming.py:2109-2127 (+ twin :3128-3147, handler :2412-2450) CONFIRMATION is terminal then unguarded _finalize_run(AWAITING_CONFIRMATION): raise → ERROR frame after terminal + FAILED write racing AWAITING park | med | confirmed | open |
| S2-M4 | streaming.py:1435-1462 + submission key f"agent-stream:{uid}:{cmid}" omits thread → retry aimed at owned thread B replays thread A's frames | med | confirmed | open |
| S2-M5 | streaming.py:1440-1454 accepted-but-never-dispatched run: 50×0.1s poll → INTERNAL frame; orphan row holds thread slot via _ensure_thread_idle | med | confirmed | open |
| S2-M6 | streaming.py:2522,:2844 confirm mints fresh _SeqEmitter (seq=1) + overwrites active pointer; legacy cursor w/o opt-in ?stream= silently skips early confirm frames incl approval gate | med | confirmed | open |
| S2-M7 | streaming.py:2218-2233,:2299 non-canonical persist: done emitted before background assistant-row write; failure warning-only (flag default off :676-680) → reload shows user row, no answer | med | confirmed | open |
| S2-M8 | streaming.py fast-path persist/checkpointer/compile/resync/aupdate OUTSIDE asyncio.timeout (:456-515 closes pre-tail); graph setup :1563-1724 + interrupt-park finalize :2120 outside timeout(300) → hung checkpoint stalls request indefinitely | med | configuration-dependent | open |
| S2-M9 | streaming.py:1342,:2520 held→:2457,:3429 dedicated AsyncSessionLocal pinned entire generator life incl ≤600s replay loop (Redis-only work) → pool exhaustion under concurrency | med | confirmed | open |
| S2-M10 | threads/stream.py:196 + stream_service.py:207,295,338,374 legacy v1 leaks raw str(exc) to client SSE payloads at 5 sites — violates client_safe_error discipline agent paths enforce | med | confirmed | open |
| S2-M11 | threads/stream.py:40,:107-111,_130 _active_streams check-then-add TOCTOU + per-process only → multi-worker concurrent streams per thread possible | med | confirmed | open |
| S2-M12 | streaming.py:1607-1617 + project_memory_service.py:38-43 recall query has NO org/user filter; tenancy rests on call-order invariant (_resolve_and_bind_project :1604). Any future raw-id caller leaks cross-tenant memories into prompts | med | latent | open |
| S2-M13 | run_event_types.py:130-135 ToolCompletedPayload.result_preview(2000c)/error(1000c) no redaction validator vs redacted args; ZERO producers today → wired unredacted gate awaiting first caller | med | latent | open |
| S2-M14 | observability.py:150-160 hide_io computed from LANGSMITH_HIDE_IO but enforced via setdefault of DIFFERENT names; injected LANGCHAIN_HIDE_INPUTS=false wins; log :170 claims True | med | configuration-dependent | open |
| S2-M15 | agent_run_tasks.py:306-334,:396-421 SSE runs stamped updated_at once, no lease/heartbeat (claim_execution celery-only); safety = STALE_AFTER 1800s vs timeout 360s pure config margin; drift ⇒ sweeper kills live run, real terminal hits guarded non-terminal UPDATE, ledger stays FAILED after answer delivered | med | configuration-dependent | open |
| S2-M16 | execute.py:494-541 threadless /execute creates NO durable agent_runs row → pod crash loses turn entirely; poller 404s after Redis expiry; sweeper/sweeper-idempotency blind | med | latent | open |
| S2-M17 | execute.py:643-645 Redis-outage job read swallowed→None→hard 404 "Job not found" on /confirm (no PG fallback unlike poll :581-598) — user told parked HITL run vanished during outage | med | confirmed | open |
| S2-M18 | seam: post-terminal ERROR coalesced into SAME chunk as CONFIRMATION renders client-side and destroys pending approval card (useChatStreaming :1037-1043 skips replacePreservingApproval when streamHadError); cross-chunk benign | med | confirmed | open |
| S2-M19 | seam: injected search_fn contexts (_nodes_rag.py:828-832, state.py:20) bypass float() score coercion + shape validation; string score survives normalizeCitation ??0 → .toFixed(2) TypeError crashes persisted bubble (retrieval-chunks.tsx:87); also unbounded item text on SSE path | med | latent | open |
| S2-M20 | toolLabels.ts:139-146 toolLabel/humanize(undefined) throws; every caller feeds unvalidated SSE fields; throw inside dispatchData try = silent step drop (service forwards data.tool raw) | med | confirmed | open |
| S2-M21 | AuiMessage.tsx:562-576 retrievalChunks maps citation.score straight through → non-numeric reaches .toFixed crash of whole streaming body (normalizeCitation coerces only ??0; hook's own toCitationCreate type-guards, authors expect non-numbers) | med | confirmed | open |
| S2-M22 | ToolExecutionCard.tsx:60-61 (+AgentMessageItem :264-277) unconditional spinner for running status, no terminal fallback; store onDone never settles leftover running executions (settleStreamingMessage only on error/stop/supersede paths) → eternal spin on finished message after dropped tool_end | med | latent | open |
| S2-M23 | AuiMessage.tsx:497-507,:597-607 dual aria-live polite regions wrap mutating lists during streaming — SR re-announces growing step list per tick + full chunk snippets per rag_context frame (timing row correctly uses off :466) | med | configuration-dependent | open |
| S2-M24 | token/reasoning_delta consumed with NO typeof-string gate (`+=`) across service/hook/store (agentChatService :279-283,:796-798,:2036-2040,:249-251,:840-842); backend truthy-gates ALL sites today (see Q2 CLOSED) → hole closed, zero defensive gate | med | latent | open |
| S2-M25 | five terminal teardowns omit streamingElapsedMs/streamingPhase/streamingStatusDetail/isRetrievingRag (useChatStreaming :1052-1061,:1097-1106,:1191-1200,:1310-1321,:2418-2429); confirm-start seeds all but isRetrievingRag (:1945-1959) → stop-during-RAG leaves stale retrieving state into next turn | med | confirmed | open |

### LOW
| ID | Finding | Sev | Class | Status |
|----|---------|-----|-------|--------|
| S2-L1 | streaming.py:1032-1047 + stream_buffer.py:101-105 corrupt Redis entry bricks replay till TTL3600 (json/model raise out of read_after unguarded; retries hit same entry) | low | confirmed | open |
| S2-L2 | streaming.py:205-218 x-request-id echoed verbatim as trace_id across envelopes/ledger/LangSmith metadata (128c cap only) | low | confirmed | open |
| S2-L3 | streaming.py:1234 cancel deadline leaves unsettled __anext__/aclose ALIVE (done-callback consumes result only); terminal committed while pull may still run | low | confirmed | open |
| S2-L4 | streaming.py:635-653 fast-path except bypasses failure-category classifier (own ValueError → internal not invalid_request) | low | confirmed | open |
| S2-L5 | streaming.py:1031,:1067-1085 replay hard-stops at 600 polls SILENTLY (>~10min streams / huge cursors) → bare close, EventSource reconnect loops dead path | low | confirmed | open |
| S2-L6 | streaming.py:618-642,:2287-2304 post-COMPLETED disconnect race: DONE yield raises GeneratorExit → cleanup finalizes CANCELLED after COMPLETED committed (absorbing semantics not visible in scope) | low | confirmed | open |
| S2-L7 | streaming.py:2622-2624 malformed DB adapter coroutine closed unawaited | low | confirmed | open |
| S2-L8 | threads/stream.py:158-165 + stream_service.py:303-341 v1 disconnect mid-LLM loses partial answer (no GeneratorExit persist branch) | low | confirmed | open |
| S2-L9 | threads/v1 no asyncio.timeout anywhere → hung Azure call holds session+slot+worker indefinitely | low | latent | open |
| S2-L10 | execute.py:771-787,:805,:1042 /stream/confirm,/cancel,/resume lack rate limiter (siblings have one) | low | confirmed | open |
| S2-L11 | execute.py:985-1039,:1111-1126 resume-no-live-stream compiles FULL graph per request just to sniff one interrupt — heavy unthrottled hot-path work | low | confirmed | open |
| S2-L12 | job_store.py:446-453,:546-549 CAS mutates shared cached dict in place, LRU recency never refreshed (no move_to_end), L1 mirror drops _confirmation_claim_id | low | confirmed | open |
| S2-L13 | execute.py:1286-1302 thread-messages default branch selects ENTIRE thread, total=len() — unbounded memory/latency on old threads | low | confirmed | open |
| S2-L14 | observability.py:505-536 first-token SLI labels route at record time; pre-set_route tokens bucket as route="pending" skewing TTFT histogram | low | latent | open |
| S2-L15 | _prompts.py:166-177 vs :310-317 SHARED_AGENT_RULES contradicts itself: auto-pick best-match project vs never pick unnamed project → nondeterministic save targets | low | spec gap | open |
| S2-L16 | job_store.py:282-301 monotonic Redis guard GET-then-SET non-atomic, created_at-only compare, _seq tiebreaker unused in Redis comparison | low | confirmed | open |
| S2-L17 | agentChatService.ts:364-366 JSON.parse fail drops frame console.warn-only; no counter/gap signal — silent content corruption in live answer (server row heals on reload) | low | confirmed | open |
| S2-L18 | agentChatService.ts:642,:653-656 no Content-Type check; proxy HTML blockpage → generic INCOMPLETE_STREAM_ERROR masking cause | low | confirmed | open |
| S2-L19 | agentChatService.ts:404-417 framing strictness: `data:{` (no space) dropped; multi-data-line events dispatched per-line as separate failing parses; spec-conformant senders break | low | spec gap | open |
| S2-L20 | agentChatService.ts:400,:429-434 TextDecoder final flush missing → multibyte tail split at last boundary lost | low | confirmed | open |
| S2-L21 | useChatStreaming.ts:1644-1646 deprecated slice stopStreaming load-bearing every hot Stop; slice reset omits steps/plan/progress/reasoning/elapsedMs/phase/detail | low | confirmed | open |
| S2-L22 | agentChatStore.ts:488-576 SSE death after server persist falls through to durable fallback → SECOND execution: duplicate rows on reload + doubled tool side effects (confirmation case guarded only) | low | confirmed | open |
| S2-L23 | useSlashCommands.ts:319 + useChatComposerActions.ts:155-158,:184-187 untracked setTimeout dispatches handleSubmit; ignored promise rethrows (:1568-1574) → unhandled rejection + post-unmount stream from dead refs | low | confirmed | open |
| S2-L24 | useChatStreaming.ts:394-396,:447,:498-506 pendingConfirmations strand if gated thread abandoned; streamIdByThreadRef unbounded for mount life (contrast activity store MAX_RUNS=20) | low | confirmed | open |
| S2-L25 | useChatStreaming.ts:1234-1237 sidebar messageCount closure vs length-dep drift (same-length swaps read stale array; impact nil today) | low | confirmed | open |
| S2-L26 | useChatStreaming.ts:1675-1748 RESUME_MAX_ATTEMPTS exhausted → keepRunOnFailure throw strands 'running' record; transportFailure deliberately not requeued; invisible until thread deactivate/reactivate | low | confirmed | open |
| S2-L27 | useChatStreaming.ts:2410-2413 confirm finally cancels SHARED rAF unconditionally vs ownership-guarded equivalent — single-flight makes harm unreachable today; trap | low | latent | open |
| S2-L28 | agentChatService.ts:799-848 durable-run endpoints send NO Authorization header + relative /api/trigger/* URLs — auth/tenant hinges on Next route injection, invisible client-side | low | configuration-dependent | open |
| S2-L29 | stores/agentActivityStore.ts:114-124 MAX_RUNS eviction ignores run.state — evicting a 'running' run destroys its seq/streamId resume cursor; >20-thread session detaches slow runs permanently | low | confirmed | open |
| S2-L30 | agentChatStore.ts:429-446 widget onDone does not settle running tool executions (asymmetric with :457-467,:1336-1339) → dropped tool_end commits permanent spinner in persisted bubble | low | confirmed | open |
| S2-L31 | markdown-utils.ts:33-37 fence parity counts col-0 ``` only; indented fences invisible; 4-backtick fences miscounted + wrong closer appended | low | confirmed | open |
| S2-L32 | AgentMessageItem.tsx:119-123 streamed markdown rendered raw — no completeStreamingMarkdown pass (unlike AuiMessage :615) → unclosed fence degrades body-to-EOF mid-stream reflow | low | confirmed | open |
| S2-L33 | AgentMarkdownRenderer.tsx:87-98 react-markdown ^10.1.0 no longer passes inline prop; heuristic fallback flips single-fenced-no-lang between inline/block mid-stream | low | confirmed | open |
| S2-L34 | AgentMarkdownRenderer.tsx:236-245,:283-286 citation-mode p override returns span → block markdown inside yields invalid nesting warnings SSR | low | configuration-dependent | open |
| S2-L35 | useArtifactContent.ts:21-34 queries fire unconditionally (no enabled guard) — malformed artifact id issues doomed request → error card | low | latent | open |
| S2-L36 | seam: call_id omitted whenever LangGraph event lacks run_id (streaming.py:832-835) → FE name-matching fallback cross-settles two concurrent SAME-tool invocations (mis-attributed durations/results) | low | latent | open |
| S2-L37 | seam: backend cannot distinguish legacy client from this-run cursor — stream param optional server-side (execute.py:1046-1055); non-FE consumers resuming across confirm boundary skip frames 1..N silently | low | spec gap | open |
| S2-L38 | seam: partial Redis failure ordering → stored cursor points at trimmed list while active pointer belongs to newer run → 204-abandon marks still-live run 'done' client-side; reload reconciles | low | latent | open |

### INFO
S2-I1 streaming.py:1288 keepalive wall-clock marker (all wire heartbeats recompute monotonic; value dead) | info | confirmed
S2-I2 streaming.py:2527,:2538 duplicate dead persist_partial_stop init 11 lines apart | info | confirmed
S2-I3 observability orphan-run lifecycle on disconnect/finalize: Unknown from services scope (no API surface; finalize lives in contract file) | info | Unknown
S2-I4 agentChatService.ts:420-423 lines after terminal in same chunk never dispatched (forward-compat hazard only) | info | spec gap
S2-I5 watchdog StreamStalledError surfaces category 'exception' — honest but indistinguishable from bugs in telemetry | info | confirmed
S2-I6 seq rAF trailing flush at terminal is intentional/benign (unmount flushes correctly :581-594) | info | confirmed
S2-I7 agentActivityStore parallel same-tool dedupe collapses rail steps vs per-invocation transcript | info | spec gap
S2-I8 seam: wall-clock marker would render absurd elapsed if ever yielded unconverted (latent drift hazard) | info | latent

## Seam verdicts (reviewer)
Q1 terminal-after-terminal: CLOSED live-wire / residual same-chunk HITL-card kill (S2-M18); Q2 token string invariant: CLOSED today, FE gate absent (S2-M24); Q3 rag_context shape: LATENT via search_fn injection (S2-M19); Q4 seq/Last-Event-ID silent-skip: REFUTED for current FE (always pins sid+after; mismatch → protective 204), server param optional (S2-L37); Q5 tool fields: CLOSED (name always present; tool_end-without-start not found, FE tolerates); Q6 enums: byte-exact 14/14 + terminal/error sets agree, unknown events skipped silently; Q7 done payload: CLOSED (all FE derefs guarded); Q8 double-render: fails to construct — cursor+sid protection total in current wiring.

## Prior-ledger reconciliation (S-* from streaming-audit-2026-08-24)
CONFIRMED (shifted where noted): H1→S2-L3(+mechanism intact), MH1→S2-M4, M1→S2-M13(latent)+durable half, M2→S2-M14, M4→S2-M2(extended PLAN/REFLECTION), M5(spec gap, zero producers), M6→S2-M15(config-dependent), M7→S2-M6, M8→S2-M7, M9→S2-M5, M10→S2-M3, M11→S2-M9, M12→S2-M8(BROADER: graph setup too), M13(latent), M14→S2-M1(extended fast-path), M15→S2-M17(confirm half)/poll-half REFUTED(PG fallback exists), M16→S2-M24(latent), MH2→S2-M25, M17→S2-M20, M18→S2-stop-window CONFIRMED(:1593-1605 vs :1423-1491,:792), M19 split cloud→confirmed/widget→S2-M22, M20→S2-refresh-failure CONFIRMED(:1221-1243+messageSlice:239-277), M22 split a11y→S2-M23/index-key shifted reasoning-panel:70+cap16, M23→S2-M10, M24→S2-M11, L1..L4,L6..L26,L28,L30 mostly CONFIRMED with new lines; L5 REFUTED(comment matches contract now); L7 SHIFTED+:1288 downgraded info; L9 SHIFTED direction revised(agent persisted count UNcapped; ≤5 was legacy dialect); L12-L15,L17,L18,L20-L23 CONFIRMED new locs; L19 REFUTED-benign-half+latent-half→S2-L27; L24 REFUTED(index-suffixed keys); L25 CONFIRMED(turn-start seeds now :753-767, still omits citations? — hook owner listed omissions only for phase/elapsed/detail/isRetrievingRag; treat citations-reset parity OPEN question folded into S2-M25 sweep); L27 DraftStatusPanel/DraftGenerationProgress: files ABSENT at pinned SHA → REFUTED-by-absence; L29 REFUTED(rail maps error honestly).
H2 consumer-crash half REFUTED at this SHA (no rag_context envelope map remains; migrated to contract-layer latents S2-M19/M24).

## Log
- 2026-08-25: audit executed under enforced isolation (launcher selftest lineage). 4 owners + 1 reviewer, zero overlap (partition_check OK, 30 files). Verify receipt: byte-identical worktree, HEAD pinned, primary untouched. Totals: 1 HIGH, 25 MED, 38 LOW, 8 INFO = 72 findings (vs tainted v1: 59 hypotheses → 48 confirmed/shifted-confirmed, 6 refuted, rest absorbed). Net-new vs v1: S2-H1 fast-path run_id (HIGH), S2-M16 threadless durable-row gap, S2-M18 same-chunk HITL kill, S2-M19 search_fn score poisoning, plus seam/coverage extensions.
- Fix-order suggestion: S2-H1 + S2-M1 (one PR: emitter run_id discipline + append observability) → S2-M3/M6 (terminal/finalize guard + seq continuity) → S2-M2 (byte bounds) → S2-M14/M15/M8 (config hardening: env force-set, lease heartbeat, timeout scopes) → S2-M10/M11 (legacy v1) → FE batch M20-M25 → lows.
