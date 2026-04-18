# K-Dense Competitive Gap Analysis

**Date:** March 2026
**Competitor:** K-Dense Web (k-dense.ai)
**Output:** `brand/gap-analysis.html`

## Summary

Analyzed K-Dense's capabilities against NOUS and identified 11 feature gaps across 3 priority tiers. All gaps tracked as Linear issues (GOO-187 through GOO-197).

## Critical Gaps (Urgent)

1. **No sandboxed code execution** (GOO-187) — K-Dense dynamically writes/executes Python from 500K+ packages. NOUS has 12 fixed tools only.
2. **Limited external DB connectors** (GOO-188) — NOUS: 3 external APIs. K-Dense: 250+ databases.
3. **Minimal scientific file formats** (GOO-189) — NOUS: 8 general types. K-Dense: 200+ domain-specific.
4. **Limited autonomous execution** (GOO-190) — NOUS: 8-10 tool loops. K-Dense: multi-hour workflows.

## High Priority Gaps

5. **No publication-ready outputs** (GOO-191) — No LaTeX, matplotlib, PPTX generation.
6. **No domain specialization** (GOO-192) — General-purpose only, no vertical expertise.
7. **No multi-agent architecture** (GOO-193) — Single StateGraph vs hierarchical agents.
8. **No ML model training** (GOO-194) — Can't train/evaluate models in workflows.

## Medium Priority Gaps

9. **No compliance certs** (GOO-195) — Security foundations exist, formalization needed.
10. **No use case gallery** (GOO-196) — No public proof of research capabilities.
11. **No R language support** (GOO-197) — Python-only, many researchers use R.

## NOUS Strengths (vs K-Dense)

- Real-time SSE/WebSocket streaming (K-Dense is async/job-based)
- Native Neo4j knowledge graph (K-Dense doesn't have this)
- Full Next.js frontend with conversational UX
- Human-in-the-loop safety controls
- Self-hosted / open architecture (data sovereignty)

## Keystone Dependency

GOO-187 (code execution sandbox) blocks GOO-191, GOO-194, and GOO-197. Start there.
