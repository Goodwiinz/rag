# Audit ledger template

Copy this header into every new audit ledger. A ledger without provenance is
invalid: findings that cannot be tied to an immutable SHA are not reproducible.

```markdown
# <audit title> — started YYYY-MM-DD

## Provenance
- session_id: <slug-timestamp-pid from launch_audit.sh>
- checkout: /absolute/path/to/.audit-worktrees/<repo>/<session>/worktree (read-only)
- ref: origin/<branch>
- sha: <40-char commit SHA the audit read>
- primary_head_at_launch: <SHA> (primary untouched by this audit; attach the archived <session>.verify.receipt)
- dirty_status_at_launch: <N modified/untracked files, hash from session.env>
- launched_at: <UTC ISO8601>
- isolation: launch_audit.sh launch --ref <ref> --slug <slug>

## Scoped-file manifest
| path | bytes | lines | coverage |
|------|-------|-------|----------|
| backend/src/api/agent/streaming.py | 118432 | 3342 | complete |
| frontend/src/hooks/chat/useChatStreaming.ts | 89211 | 2394 | complete |
| ...  |  |  | partial — lines 1–800 only |

Coverage rule: an "every line audited" claim requires every scoped row marked
`complete`, with bytes/lines recorded at audit time. Partial rows invalidate
the claim; say so in ## Log instead.

## Findings
| ID | Finding (one line) | Sev | Class | Status | Owner | PR | Updated |
|----|--------------------|-----|-------|--------|-------|----|---------|

Class (mandatory, one of):
- confirmed — defect reproducible at the pinned SHA
- configuration-dependent — defect only under deploy/config states outside the repo
- latent — no current trigger; becomes a defect when adjacent code changes
- spec gap — code matches spec, spec is wrong or silent
- Unknown — could not determine; name what evidence is missing

Zero findings is a valid outcome. Never inflate counts to hit a quota.
```

## Retrofitting older ledgers

If provenance was not recorded (pre-launcher audits), add the block with honest
values: `sha: UNRECORDED — audit ran against mutable primary checkout` and note
the violation in `## Log`. Never invent a SHA after the fact.
