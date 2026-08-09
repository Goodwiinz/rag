Status: approved

Capability: exercise the human-in-the-loop (HITL) interrupt *lifecycle* itself
— approve, reject, double-confirm, confirm-after-resolution, and cancel-while-
parked — rather than only the ordering invariant (interrupt fires before
mutation) that every other HITL-bearing task in this suite already asserts.
This is the safety-critical path every prior capability assumes works but
none of them tests directly.

Request (four independent single-turn sessions, one per phase, same
synthetic org/workspace):

1. Approve-once: `Create a research project named "HITL Approve And Reconfirm".`
2. Reject: `Create a research project named "HITL Reject Path".`
3. Re-confirm-resolved: no new request — the harness re-issues
   `POST /confirm/{job_id}` twice more against phase 1's already-resolved job.
4. Cancel-while-parked: `Create a research project named "HITL Cancel While Parked".`

Initial conditions: one synthetic organization/user/workspace with zero
projects. Each phase runs `create_project` — the same tool exercised by the
project-management capability — so the only variable under test is the
lifecycle around its interrupt, not tool selection or argument threading.

Why this requires the capability: a graph that merely orders "interrupt
before mutation" (already gated by capabilities 1 and 14) can still fail
every gate below — firing the tool twice on a retried confirm, letting a
rejected interrupt leak a row, treating a resolved job's second confirm as a
fresh approval, or silently dropping a parked interrupt on cancel so it can
never be redelivered. Only a graph whose interrupt/resume state machine is
itself correct passes all six.

Pass iff (six objective gates, verbatim from `AGENT_FLOW_BASELINE.md` §8):

1. The interrupt payload names the tool and its arguments **exactly** — the
   recorded `{"name": ..., "args": {...}}` block must equal the tool call the
   graph actually queued, compared by value, not by a substring match against
   any narrative text.
2. **Reject** (`confirmed: false`) resumes the graph with **zero mutations**
   — the `projects` row count for the seeded workspace is identical before
   and after resume, read independently by the verifier — **and** a coherent
   non-empty final assistant message.
3. **Approval executes exactly once.** Re-sending the same confirmation
   (e.g. a client retry before it observes the first response) must not
   fire the tool a second time: exactly one `projects` row and exactly one
   tool-execution record for that job's `create_project` call.
4. `POST /confirm/{job_id}` against an **already-resolved** interrupt is a
   no-op: it must not mutate state further, and every such repeat call must
   return the **same** HTTP status as every other repeat call (a stable,
   consistent response — not necessarily 200; see `harness.md` for why 409
   is the production shape here).
5. **Cancel while parked** leaves the interrupt **re-deliverable**: polling
   the parked job after the client disconnects/cancels must keep returning
   the identical `confirmation` payload (same tool, same args) rather than
   losing or mutating it — capability 3's confirm-path idempotency rule
   applied to the HITL-parked case specifically.
6. The LangGraph checkpointer connection string is `postgresql://` (psycopg
   v3). A `postgresql+asyncpg://` URL is an **infrastructure failure**
   (`InfrastructureFailure`, verifier exit 2) — it means the environment
   wired the wrong driver, not that the agent behaved incorrectly — so it
   must never be scored as a gate failure (exit 10).

**Semantic gate:** N/A (counts as pass) — none of the five phases produces a
judgeable answer; correctness here is entirely state-machine behavior.

Verifier: deterministic trajectory and independent-database-state checks. No
LLM judge.

Verifier evidence: per-phase interrupt payload (tool + args) and its
`approved_at`/`rejected_at` timestamp; the confirm-repeat records (HTTP
status, row counts) for phase 3; the parked-job poll records (confirmation
payload per poll) for phase 4; the final assistant message for phases 1 and
2; the checkpointer's resolved connection string scheme; and the verifier's
own independent read of the `projects` table for the seeded workspace.

Accepted alternatives: any internal plan that reaches the same interrupt
before the same mutation is accepted — this task does not require a specific
route or classifier source, only the lifecycle behavior around the pause.
Extra read-only tool calls before or after the interrupt are permitted.
