# Glossary

Workplace shorthand, acronyms, and internal language for the NOUS project.

## Acronyms

| Term | Meaning | Context |
|------|---------|---------|
| RAG | Retrieval-Augmented Generation | Core system architecture |
| SSE | Server-Sent Events | Agent streaming protocol |
| RBAC | Role-Based Access Control | Auth system |
| HITL | Human-in-the-Loop | Agent interrupt pattern for destructive ops |
| KG | Knowledge Graph | Neo4j entity/relationship store |
| MCP | Model Context Protocol | Tool/plugin integration standard |
| E2B | Sandboxed code execution platform | Gap analysis recommendation |

## Internal Terms

| Term | Meaning |
|------|---------|
| subgraph | Specialized agent routing path (research, writing, data, general) |
| tool loop | One iteration of the agent calling a tool and processing results |
| intent classifier | LangGraph node that routes queries to the right subgraph |
| destructive tool | Agent tool that modifies data (ingest, create_note, create_draft) — triggers HITL |
| gotchas | Known pitfalls documented in CLAUDE.md |
| hot cache | CLAUDE.md working memory (top 30 people/terms) |
| checkpoint | AsyncPostgresSaver state snapshot for agent recovery |
| circuit breaker | Resilience pattern protecting Neo4j, Qdrant, Cohere connections |

## Project Codenames

| Codename | Project |
|----------|---------|
| NOUS | Multimodal Intelligence Platform (Greek: νοῦς — mind/intellect) |
| Goodwiinz | Linear team name |

## Tools & Services

| Tool | Used for | Port |
|------|----------|------|
| PostgreSQL | Primary relational DB | 5432 |
| Neo4j | Knowledge graph | 7687 |
| Qdrant | Vector search | 6333 |
| Redis | Cache + message broker | 6379 |
| MinIO | S3-compatible object storage | 9000 |
| Celery | Background task queue | — |
| Flower | Celery monitoring dashboard | 5555 |
| Adminer | DB admin UI | 8080 |
| LangSmith | Agent tracing + observability | — |
| Prometheus | Metrics collection | — |

## External Integrations

| Service | What it does |
|---------|-------------|
| arXiv API | Academic paper search and ingestion |
| Crossref API | Citation metadata resolution |
| NCBI API | Biomedical literature access |
| OpenAI | Chat completions + embeddings |
| Anthropic | Alternative LLM provider |
| Azure OpenAI | Multi-endpoint LLM (chat, embedding) |
| Cohere | Search result reranking |

## Brand Terms

| Term | Meaning |
|------|---------|
| Ink | Primary dark color `#0A0A0E` |
| Surface | Light background `#F7F7F5` |
| Accent | Indigo `#6366F1` |
| Accent Soft | Light indigo `#818CF8` |
| Highlight | Violet `#A78BFA` |

## Competitive Terms

| Term | Meaning |
|------|---------|
| K-Dense | Competitor — autonomous AI agent platform for scientific research |
| BioServices | Python package providing ~70 scientific database connectors |
| BioPython | Python package for 38 NCBI database access |
| E2B | Code execution sandbox service (gap analysis recommendation) |

## Linear Issue References

| ID | Title | Priority | Phase |
|----|-------|----------|-------|
| GOO-187 | Sandboxed code execution | Urgent | Phase 1 |
| GOO-188 | External database connectors | Urgent | Phase 2 |
| GOO-189 | Scientific file format parsers | Urgent | Phase 2 |
| GOO-190 | Extended agent autonomy | Urgent | Phase 1 |
| GOO-191 | Publication-ready outputs | High | Phase 3 |
| GOO-192 | Domain-specific verticals | High | Phase 3 |
| GOO-193 | Multi-agent architecture | High | Phase 4 |
| GOO-194 | ML model training | High | Phase 1-2 |
| GOO-195 | SOC 2 / HIPAA compliance docs | Medium | Phase 4 |
| GOO-196 | Public use case gallery | Medium | Phase 3 |
| GOO-197 | R language support | Medium | Phase 4 |
