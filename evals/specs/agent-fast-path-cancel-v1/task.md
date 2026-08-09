Status: approved

Capability: `AGENT_FLOW_BASELINE.md` §13, "Luna fast path" — capability 3's
("Stream cancellation durability") cancel/partial-persistence invariants,
applied to the fast-path route (`backend/src/services/agent/fast_path.py` +
`backend/src/api/agent/streaming.py:_stream_luna_fast_path`) instead of the
LangGraph route. Unblocked by #1353, which fixed the fast path's
emit-before-append ordering and cancel-linkage defects; regression-tested at
the unit level by
`backend/tests/api/agent/test_stream_fast_path.py::test_fast_path_cancel_links_partial_and_keeps_prefix`.

**Reference implementation — read, do not modify:**
`evals/agent-stream-cancel-durability-v1` (capability 3, digest-pinned). This
task mirrors its cancel/partial-persistence invariants onto the fast-path
route; where the fast path's real behavior differs from the graph path, this
document states the difference explicitly rather than forcing a false
parallel (see "Known differences from capability 3" below).

**THE KNOWN, CORRECT TOLERANCE — state verbatim, this is not a bug to fix:**
the fast path's own `CancelledError` handler (`cancel_fast_path` in
`_stream_luna_fast_path`) persists the stopped partial row and issues the
FIRST `run.cancelled` finalize, with `payload.assistant_message_id` naming
that row — this is the linked, durable call. The `CancelledError` then
propagates out of `_stream_luna_fast_path`'s `async for` into
`stream_event_generator`'s own outer, route-agnostic `CancelledError`
handler, which fires a SECOND, unlinked `run.cancelled` finalize (its
`persisted_assistant_id` is a separate, never-populated local for the
fast-path branch). In production this second call is a no-op:
`finalize_submission`'s terminal-status `UPDATE ... WHERE status NOT IN
(...)` guard and `append_event`'s `RunAlreadyTerminalError` (backed by the
`uq_agent_run_events_one_terminal` partial unique index) both absorb it —
only the first, linked event is ever durably persisted.

**Acceptance criterion (verbatim, the exact tolerance the verifier encodes):**
The verifier MUST PASS when it sees one linked finalize plus at most one
absorbed unlinked duplicate. The verifier MUST FAIL when the LINKED event is
missing (even if the unlinked one is present). A verifier that treats the
duplicate itself as a failure would fail every honest run — that is the trap
this capability exists to avoid falling into.

**Objective gates (capability 3's invariants, applied to the fast-path
route):**

1. **Emit-before-append ordering.** A model chunk's text may be appended to
   the in-memory partial (and therefore become eligible for persistence)
   only after its SSE emit has completed. `fast_path.py`'s streaming loop
   buffers the frame via `emitter.emit()` and only appends to `parts` on a
   successful return — a cancellation raised inside `emitter.emit()` must
   never let that chunk's text reach the persisted partial. Encoded from
   `stream_event_generator`'s comment: "Buffer BEFORE recording for
   persistence — same ordering invariant as the graph path: the stopped
   partial must stay a prefix of the buffered stream, so a cancellation
   inside this await can only lose the last chunk, never invent one."
2. **Cancel linkage.** The durable terminal event for a cancelled fast-path
   run is `run.cancelled` and its payload carries `assistant_message_id`
   equal to the id of the persisted partial row — not merely that *some*
   finalize attempt in the adapter's own log claims a link (see the
   tolerance above: the independent DB read is authoritative, not the
   adapter's self-reported attempt log).
3. **Partial persisted and linked to the run.** A stopped (`stopped=true`)
   assistant message row exists with non-empty content, and the `AgentRun`
   row's projected `status` is `cancelled`.
4. **Prefix retained.** The persisted partial content equals exactly the
   concatenation, in order, of every chunk whose emit completed and was
   appended — never truncated mid-chunk, never extended with content beyond
   the last successfully-emitted chunk.

**Known differences from capability 3 (documented, not forced into a false
parallel):**

- Gate 3's `AgentRun.assistant_message_id` assertion is **not** a fast-path
  novelty — it mirrors an assertion capability 3's own digest-pinned
  verifier already makes (`evals/agent-stream-cancel-durability-v1/tests/verify.py:442`,
  `if run.get("assistant_message_id") != assistant.get("id")`). Both routes
  share the same `finalize_submission` (`backend/src/services/agent/agent_submission_service.py:696-753`),
  which projects `payload.assistant_message_id` onto the `AgentRun` column
  for any route, and the graph route's own `cancel_current_stream()`
  (`backend/src/api/agent/streaming.py:1327-1353`) populates it the same
  way. `AGENT_FLOW_BASELINE.md` §3's table previously claimed this column
  "is never written by any code path and stays NULL" — that row was stale
  and has been corrected; it contradicted capability 3's own verifier.
- Capability 3 has no second, unlinked finalize attempt in its documented
  invariants (its `CancelledError` handler is the only one on that route).
  The fast path's second, absorbed, unlinked finalize is a fast-path-only
  structural feature of `stream_event_generator` wrapping
  `_stream_luna_fast_path`, and is the entire reason this task's tolerance
  gate exists.
- Capability 3 exercises the LangGraph route's Redis SSE replay buffer in
  depth (buffer TTL, buffered-frame content matching). This task's gates
  focus on the emit/append/finalize ordering specific to the fast path and
  do not re-assert the shared Redis replay-buffer mechanics capability 3
  already covers for the same `_SeqEmitter`/`stream_buffer` code paths.

**Semantic gate:** N/A (counts as pass — no answer to judge on cancellation,
same rationale as capability 3).

Verifier: deterministic, no LLM judge. Independent state cross-check reads
`agent_runs`, `agent_run_events`, and `chat_messages` directly through the
verifier's own psycopg connection, never trusting the adapter's self-reported
`finalize_attempts` log as the durable signal — same anti-fabrication posture
as `agent-hitl-lifecycle-v1` and `agent-stream-cancel-durability-v1`.

Accepted alternatives: none for gates 1-4 (they are the literal contract
`test_fast_path_cancel_links_partial_and_keeps_prefix` pins). The only
accepted variation is the tolerance itself: zero or one unlinked duplicate
finalize attempt in the adapter's own log, and zero or one absorbed
(non-durable) unlinked terminal-event write attempt — never more than one of
either, and never a durable ledger with two terminal events (the partial
unique index makes that a database-integrity violation, not a valid
outcome).
