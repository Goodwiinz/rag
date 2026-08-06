export const meta = {
  name: 'audit-thread-project-attach',
  description: 'Swarm audit of thread→project attach feature for bugs across 8 dimensions with adversarial verification',
  phases: [
    { title: 'Find', detail: '8 parallel finders, one per audit dimension' },
    { title: 'Verify', detail: '2 adversarial skeptics refute each finding' },
    { title: 'Critic', detail: 'completeness critic — what was missed' },
  ],
}

const SHARED = `
FEATURE UNDER AUDIT: thread→project attach in the NOUS RAG platform (FastAPI + SQLAlchemy async + PostgreSQL).

A thread→project link is stored in TWO places that must stay in sync:
  (A) scalar columns on the thread: Thread.source_project_id (FK collections.id, ondelete SET NULL) + Thread.rag_document_scope (JSONB snapshot {"document_ids":[...]})
  (B) a junction row in project_threads (ProjectThread: project_id, thread_id, link_type, linked_by_id, linked_at, context_note)

KEY FILES (read them line-accurately before reporting):
  - backend/src/services/research/project_thread_service.py  (attach_thread_to_project helper + get_project_document_scope) — 80 lines, the "single source of truth" writer
  - backend/src/api/research/project_chat.py  (637 lines): start_chat_from_project (L142-276), link_thread_to_project (L284-364), list_project_threads (L372-434), unlink_thread_from_project (L442-523), save_thread_to_note (L531-637), _get_project_with_auth (L55), _get_thread_with_auth (L88), _get_project_document_scope (L122)
  - backend/src/api/threads/threads.py  (create_thread auto-link path L188-252)
  - backend/src/models/project_thread.py  (ProjectThread model; note __init__ default + datetime.utcnow naive)
  - backend/src/models/thread.py  (Thread model; source_project_id ondelete SET NULL, rag_document_scope JSONB)
  - backend/alembic/versions/i4k8l9m0n1o2_add_project_thread_integration.py  (DB schema; has UniqueConstraint('project_id','thread_id', name='uq_project_thread'))
  - backend/src/api/agent/jobs.py, backend/src/api/agent/execute.py, backend/src/api/agent/streaming.py  (READ path: how the agent consumes source_project_id / rag_document_scope; AGENT_THREAD_MARKER)

CONFIRMED FACTS (do not re-litigate, build on them):
  - The DB migration DOES declare uq_project_thread unique(project_id, thread_id). The SQLAlchemy ProjectThread model does NOT declare this constraint in __table_args__ (drift).
  - attach_thread_to_project does a SELECT-then-INSERT idempotency check with no locking (TOCTOU).
  - start_chat_from_project does NOT call attach_thread_to_project — it writes thread.source_project_id, rag_document_scope, AND a ProjectThread row by hand.
  - create_thread auto-link is best-effort: on exception it logs + rolls back and still returns 200/201 (silent partial).
  - 500 handlers interpolate str(e) into the HTTP detail (potential info leak).

YOUR JOB: find REAL bugs (not style nits). For each finding give: title, severity (critical/high/medium/low), file, lines, category, precise description, concrete impact, repro/trigger, and a specific fix. Be concrete and grounded in actual code lines. Do NOT invent code that isn't there — read the files.
`

const FIND_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          file: { type: 'string' },
          lines: { type: 'string' },
          category: { type: 'string' },
          description: { type: 'string' },
          impact: { type: 'string' },
          repro: { type: 'string' },
          fix: { type: 'string' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
        required: ['title', 'severity', 'file', 'lines', 'description', 'impact', 'fix', 'confidence'],
      },
    },
  },
  required: ['findings'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['confirmed', 'refuted', 'uncertain'] },
    reasoning: { type: 'string' },
    corrected_severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
    is_duplicate_or_style: { type: 'boolean' },
  },
  required: ['verdict', 'reasoning', 'corrected_severity', 'is_duplicate_or_style'],
}

const DIMENSIONS = [
  { key: 'atomicity', prompt: `DIMENSION: Transaction atomicity & two-place desync.
Audit whether (A) scalar thread columns and (B) the project_threads row can ever land out of sync, or be partially committed. Scrutinize: start_chat_from_project bypassing the helper; the order of db.flush/db.add/db.commit; create_thread auto-link committing in a separate unit after the thread was already created+committed by the chat service (does rollback there actually undo anything? what does it leave behind?); whether db.refresh after a reused-existing link works; nested/double commits; what happens if get_project_document_scope throws mid-attach.` },
  { key: 'concurrency', prompt: `DIMENSION: Concurrency, idempotency & race conditions.
The idempotent attach does SELECT-then-INSERT with no row lock, and the DB has uq_project_thread unique(project_id,thread_id). Audit: TOCTOU between two concurrent link/create requests for the same (project,thread) → IntegrityError surfacing as 500 instead of idempotent success; lost-update on rag_document_scope when two attaches race; whether the unique violation is caught/handled anywhere; double-submit from the UI. Also concurrent start_chat creating the same conversation.` },
  { key: 'authz', prompt: `DIMENSION: Authorization & tenant isolation.
Audit every auth path: _get_project_with_auth and _get_thread_with_auth (do they correctly scope by Workspace.owner_id? what about shared/collaborator workspaces?); the same-workspace check in link and start_chat; CRITICAL — in unlink_thread_from_project the reassignment picks remaining_link.project_id and copies its document scope WITHOUT re-checking the user owns that project — can a thread's source_project_id/rag_scope be repointed to a project across an auth boundary? Also: does list_project_threads leak threads the caller shouldn't see? IDOR on thread_id/project_id path params.` },
  { key: 'ragscope', prompt: `DIMENSION: RAG document scope correctness & staleness.
rag_document_scope is a SNAPSHOT taken at attach time. Audit: staleness when documents are later added/removed/soft-deleted from the project (does the agent query stale doc IDs? include deleted docs? miss new ones?); the two DIFFERENT scope-fetch functions (project_thread_service.get_project_document_scope vs project_chat._get_project_document_scope) — do they diverge?; AGENT_THREAD_MARKER in jobs.py — what is it and does it collide with a real empty scope?; how execute.py/streaming.py/jobs.py READ the scope and source_project_id; empty-scope ({"document_ids":[]}) vs None semantics — does empty scope accidentally mean "all docs" or "no docs"?` },
  { key: 'unlink', prompt: `DIMENSION: Unlink & reassignment edge cases.
Focus unlink_thread_from_project (L442-523). Audit: the delete-then-query-remaining flow (is the deleted row excluded correctly? is it flushed before the remaining query?); reassignment to "most recent remaining link" — ordering by linked_at when linked_at is datetime.utcnow naive and could tie; setting source_project_id/rag_document_scope to None when no links remain; interaction with FK ondelete SET NULL on source_project_id; what if the thread has a ProjectThread row but source_project_id already points elsewhere; 204 response correctness; unlink of a non-existent link returns 404 but is that consistent.` },
  { key: 'errors', prompt: `DIMENSION: Error handling, silent failures & info leak.
Audit: create_thread auto-link best-effort swallow (L237-252) — it returns success while the link silently failed; does the response tell the client the link failed? does the rollback there roll back the thread itself or just the link? broad except Exception → 500 with detail=f"...{str(e)}" leaking internals/SQL; rollback-after-commit anti-patterns; bare except: pass; whether failures are observable (metrics/sentry) vs only logged. Does the agent read-path silently degrade when the link is half-written?` },
  { key: 'frontend', prompt: `DIMENSION: Frontend attach flow.
Audit these files: frontend/src/store/projectChatStore.ts, frontend/src/services/projectChatService.ts, frontend/src/hooks/useProjectChat.ts, frontend/src/hooks/useProjectChatWidget.ts, frontend/src/components/research/LinkThreadModal.tsx, frontend/src/components/research/ThreadCard.tsx, frontend/src/components/research/ProjectChatTab.tsx, frontend/src/components/context-rail/ProjectPickerPopover.tsx, frontend/src/types/project-chat.ts. Look for: optimistic-update bugs / stale list after attach/detach, missing error handling on link/unlink calls, double-submit not disabled, race between attach and navigation, type mismatch with backend response (ProjectThreadResponse fields), uuid handling, not refetching after 409/500.` },
  { key: 'modeldrift', prompt: `DIMENSION: Model/schema drift & data integrity.
Audit: ProjectThread model missing UniqueConstraint that the migration has (ORM-level dupes not prevented in tests/sqlite); ProjectThread.__init__ override + column default both set link_type/linked_at (redundant/conflicting?); datetime.utcnow (naive) written into DateTime(timezone=True) columns; link_type stored as free String(50) not an enum-constrained column (invalid values possible); FK ondelete behaviors (collections CASCADE on project_threads vs SET NULL on thread.source_project_id — consistent?); to_dict/serialization correctness; Pydantic response schema (ProjectThreadResponse) vs ORM field nullability mismatches.` },
]

phase('Find')
const results = await pipeline(
  DIMENSIONS,
  (d) => agent(`${SHARED}\n\n${d.prompt}`, { label: `find:${d.key}`, phase: 'Find', schema: FIND_SCHEMA }),
  (review, d) => {
    const findings = (review && review.findings) || []
    if (!findings.length) return []
    return parallel(findings.map((f) => () =>
      parallel([
        () => agent(`${SHARED}\n\nADVERSARIAL VERIFY (skeptic #1). A finder claims this bug in the thread→project attach feature. Your job is to REFUTE it. Read the actual code at ${f.file}:${f.lines} and surrounding context. Default to refuted=true unless the code genuinely exhibits the described bug. Is it real, or is it a misread / non-issue / pure style nit / already-handled?\n\nFINDING:\nTitle: ${f.title}\nSeverity: ${f.severity}\nFile: ${f.file}\nLines: ${f.lines}\nDescription: ${f.description}\nImpact: ${f.impact}\nProposed fix: ${f.fix}`, { label: `verify1:${d.key}`, phase: 'Verify', schema: VERIFY_SCHEMA }),
        () => agent(`${SHARED}\n\nADVERSARIAL VERIFY (skeptic #2, independent). A finder claims this bug. Read the actual code at ${f.file}:${f.lines} and trace the real control/data flow. Confirm ONLY if you can state the concrete trigger and concrete wrong outcome. If the claimed impact is overstated, downgrade severity. Mark is_duplicate_or_style=true if it's a style/cosmetic issue rather than a behavioral bug.\n\nFINDING:\nTitle: ${f.title}\nSeverity: ${f.severity}\nFile: ${f.file}\nLines: ${f.lines}\nDescription: ${f.description}\nImpact: ${f.impact}\nProposed fix: ${f.fix}`, { label: `verify2:${d.key}`, phase: 'Verify', schema: VERIFY_SCHEMA }),
      ]).then((votes) => {
        const v = votes.filter(Boolean)
        const confirmed = v.filter((x) => x.verdict === 'confirmed').length
        const refuted = v.filter((x) => x.verdict === 'refuted').length
        const style = v.some((x) => x.is_duplicate_or_style)
        // corrected severity = lowest agreed (most conservative) among confirms, else finder's
        const sevs = v.map((x) => x.corrected_severity).filter(Boolean)
        return {
          ...f,
          dimension: d.key,
          votes: v,
          confirmed_count: confirmed,
          refuted_count: refuted,
          is_style: style,
          status: confirmed >= 1 && confirmed >= refuted ? 'confirmed' : (refuted > confirmed ? 'refuted' : 'uncertain'),
          consensus_severity: sevs.length ? sevs.sort((a, b) => ['critical','high','medium','low'].indexOf(a) - ['critical','high','medium','low'].indexOf(b))[0] : f.severity,
        }
      })
    ))
  }
)

const all = results.flat().filter(Boolean)
const confirmed = all.filter((f) => f.status === 'confirmed' && !f.is_style)
const uncertain = all.filter((f) => f.status === 'uncertain' && !f.is_style)
const refuted = all.filter((f) => f.status === 'refuted')

log(`Findings: ${all.length} total → ${confirmed.length} confirmed, ${uncertain.length} uncertain, ${refuted.length} refuted`)

phase('Critic')
const critic = await agent(`${SHARED}\n\nYou are the COMPLETENESS CRITIC. Below are the CONFIRMED bugs found so far in the thread→project attach feature. Identify what the audit likely MISSED: untested code paths, a dimension not covered, an interaction between two findings, an edge case nobody traced. List up to 6 concrete gaps as additional findings (same fields). Only report things you can ground in the actual code — read files if needed. Do not repeat the findings already listed.\n\nALREADY CONFIRMED:\n${confirmed.map((f, i) => `${i + 1}. [${f.consensus_severity}] ${f.title} (${f.file}:${f.lines})`).join('\n')}`, { label: 'critic', phase: 'Critic', schema: FIND_SCHEMA })

return {
  summary: {
    total: all.length,
    confirmed: confirmed.length,
    uncertain: uncertain.length,
    refuted: refuted.length,
    by_severity: {
      critical: confirmed.filter((f) => f.consensus_severity === 'critical').length,
      high: confirmed.filter((f) => f.consensus_severity === 'high').length,
      medium: confirmed.filter((f) => f.consensus_severity === 'medium').length,
      low: confirmed.filter((f) => f.consensus_severity === 'low').length,
    },
  },
  confirmed,
  uncertain,
  refuted: refuted.map((f) => ({ title: f.title, file: f.file, lines: f.lines, why: (f.votes[0] && f.votes[0].reasoning) || '' })),
  critic_gaps: (critic && critic.findings) || [],
}
