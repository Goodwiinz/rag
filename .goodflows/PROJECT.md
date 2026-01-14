# Project: Multimodal RAG System

## Vision
Enterprise-grade Retrieval-Augmented Generation system that processes multimodal content (text, images, documents) to provide accurate, context-aware AI responses.

## Core Value
Seamless multimodal document processing with high-quality semantic search and LLM-powered answers.

## Architecture
```
Frontend (React) → API Gateway → RAG Backend (Python)
                                      ↓
                              Vector Store (Chroma/Pinecone)
                                      ↓
                              LLM (Claude/OpenAI)
```

## Tech Stack
| Technology | Purpose | Notes |
|------------|---------|-------|
| Python | Backend RAG pipeline | FastAPI |
| React/TypeScript | Frontend UI | Vite |
| Chroma/Pinecone | Vector storage | Embeddings |
| Claude/OpenAI | LLM inference | Multi-provider |
| Docker | Containerization | Monorepo structure |

## Key Decisions
| Decision | Rationale | Date | Phase |
|----------|-----------|------|-------|
| Monorepo structure | Unified versioning | - | Setup |
| Multi-provider LLM | Flexibility & fallback | - | Core |

## Boundaries
### DO
- Process text, PDFs, images for RAG
- Provide semantic search with citations
- Support multiple LLM providers

### DON'T
- Real-time streaming (batch preferred)
- Fine-tuning models (use as-is)

## External Dependencies
- anthropic: Claude API
- openai: GPT API
- chromadb: Vector store
- langchain: RAG framework
