# Audit agent prompt template

Fill the placeholders; do not add finding-count expectations anywhere in the
prompt ("expect 10–30 findings" style quotas bias agents toward quota-seeking).
Zero findings is a valid, reportable outcome.

```text
AUDIT TASK — <scope name>

Target: detached worktree at <ABS_WORKTREE_PATH>, pinned SHA <SHA>.
Handoff: <WORKTREE>/AUDIT_HANDOFF.md (prior ledgers — context only).
Primary checkout is off-limits. Do not write anywhere in this worktree.

Scope (exhaustive, every line):
<list of files/dirs>

For each scoped file you MUST record: bytes, line count, and whether coverage
was complete or partial. Report the manifest even if it contains zero findings.

Classification — tag every finding with exactly one:
- confirmed: reproducible at <SHA>
- configuration-dependent: only under deploy/config states outside the repo
- latent: no current trigger; becomes real when adjacent code changes
- spec gap: code matches spec; spec wrong/silent
- Unknown: state what evidence is missing

Evidence contract per finding:
- file:line inside the worktree
- verbatim excerpt (<= 5 lines)
- one-sentence failure scenario
- classification + why

Do NOT:
- propose fixes (that is a later phase)
- re-report findings already closed in prior ledgers
- pad with style nits that carry no runtime/behavioral consequence
```

## Partitioned audits (multi-agent)

Before dispatching agents, produce a single dependency map and assign each file
exactly one owner (see SCOPE_PARTITIONING.md). Validate with:

    python scripts/audit/partition_check.py partition.json --repo .

Rules:
1. One owner per file. Overlap is a build error, not a style issue.
2. Cross-boundary interactions (e.g. wire protocol between backend producer and
   frontend consumer) go to ONE designated reviewer agent after owners finish.
3. Each agent gets only its own scope plus the shared interface contracts —
   not other agents' file lists.
