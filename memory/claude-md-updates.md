# CLAUDE.md Update Notes

_Last reviewed: 2026-03-23_

---

## Current CLAUDE.md State

The CLAUDE.md file accurately reflects the current NOUS architecture as of 2026-03-23. No code changes were detected via GitHub today (gh CLI unavailable), so no architectural updates are confirmed.

## Potential Future Updates to CLAUDE.md

Based on Linear issues created today, the following items may require CLAUDE.md updates once implemented:

### GOO-187 — Sandboxed Code Execution (Urgent)
If implemented, add to CLAUDE.md:
- New tool: `execute_code` (Python/R sandbox, likely via e2b or Dagger)
- New gotcha: code execution tool will likely trigger `interrupt()` as a destructive tool
- New subgraph or tool node additions in `backend/src/services/agent/graph.py`

### GOO-188 — External Database Connectors (Urgent)
If implemented, add to CLAUDE.md:
- New plugin/connector architecture (adapter pattern for 250+ external databases)
- New endpoints under `/api/v1/connectors/` (TBD)
- Possible new services in `backend/src/services/`

### GOO-189 — Scientific File Format Parser Registry (Urgent)
If implemented, add to CLAUDE.md:
- Parser registry pattern (auto-format detection)
- New supported file types beyond current 8 general types
- Likely extends document ingestion pipeline in backend

### GOO-190 — Extended Agent Execution Depth (Urgent)
If implemented, update CLAUDE.md:
- Current max tool loops: 8 (Research subgraph)
- New depth: TBD (multi-hour workflows targeted)
- May change `interrupt()` policy for destructive tools
- Possible new execution strategy (branching decisions, error recovery, retry)

### GOO-193 — Hierarchical Multi-Agent Architecture (High)
If implemented, update CLAUDE.md:
- Major architectural change: current single StateGraph → hierarchical supervisor pattern
- Agent System Quick Ref section will need full rewrite
- Key files section will change

---

## Notes
- No CLAUDE.md changes are recommended at this time — no confirmed code merges
- GitHub sync was blocked (gh CLI unavailable); re-run after fixing to detect merged changes
