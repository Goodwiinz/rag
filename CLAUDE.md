# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Multimodal Enterprise RAG System** that processes text, images, audio, and video files. It follows an evaluation-first architecture with comprehensive testing and metrics tracking.

### Documentation
Comprehensive documentation is available in the [`docs/`](docs/) directory, organized by category:
- **[Architecture](docs/architecture/)** - System design and component architecture
- **[Deployment](docs/deployment/)** - Deployment strategies and CI/CD guides
- **[Database](docs/database/)** - Database schema, setup, and migration guides
- **[Security](docs/security/)** - Security audits and authentication strategies
- **[Testing](docs/testing/)** - Testing guides, reports, and validation
- **[Operations](docs/operations/)** - Monitoring, runbooks, and observability
- **[Guides](docs/guides/)** - Quick start and usage guides
- **[Fixes](docs/fixes/)** - Bug fix reports and implementation status

See the [Documentation Index](docs/README.md) for a complete overview.

## Architecture

The system is built with several key components:

- **Multi-Agent Orchestration** (`src/agents/`): Uses CrewAI for specialized agents (orchestrator, retrieval, graph, vector, QA, synthesis)
- **Multimodal Ingestion** (`src/ingestion/`): Processes PDF, TXT, JPG/PNG, MP3/MP4 files with OCR, transcription, and frame extraction
- **Knowledge Graph** (`src/knowledge_graph/`): Neo4j-powered entity and relationship management
- **Vector Store** (`src/vector_store/`): Qdrant for semantic similarity search
- **Hybrid Search** (`src/search/`): Combines vector, graph, and keyword search with reranking
- **Evaluation Framework** (`src/evaluation/`): DeepEval integration with RAG Triad metrics

## Development Commands

### Environment Setup
```bash
# Start Docker services
docker-compose up -d

# Install dependencies
pip install -r requirements.txt

# Run setup script
./setup.sh
```

### Testing
```bash
# Run all tests
pytest tests/ --cov=src --cov-report=html

# Run specific test suites
pytest tests/specs/test_evaluation_suite.py -v
pytest tests/specs/test_ingestion_pipeline.py -v
pytest tests/specs/test_knowledge_graph.py -v
pytest tests/specs/test_hybrid_search.py -v
pytest tests/specs/test_agent_orchestration.py -v

# Run evaluation benchmarks
python -m src.evaluation.deepeval_runner
```

### Running the Application
```bash
# Streamlit UI
streamlit run src/ui/streamlit_app.py

# FastAPI server
uvicorn src.ui.api_server:app --host 0.0.0.0 --port 8000

# Interactive notebook
jupyter notebook notebooks/demo.ipynb
```

## Key Design Patterns

### Evaluation-First Development
- All features are built with test specifications first using spec-kit philosophy
- Success criteria are defined in `src/evaluation/success_criteria.py`
- RAG Triad metrics: Answer Relevancy (>70%), Faithfulness (>90%), Contextual Relevancy (>70%)

### Multi-Agent Architecture
- Agents are specialized: orchestrator, retrieval, graph, vector, QA, synthesis
- Workflow types: factual_lookup, reasoning, multimodal
- Uses CrewAI for agent coordination and task execution

### Hybrid Search System
- Parallel execution of vector, graph, and keyword search
- Results are combined, deduplicated, and reranked
- Supports filtering by modality and other metadata

## Configuration

### Environment Variables
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Neo4j connection
- `QDRANT_URL`, `QDRANT_API_KEY`: Qdrant vector store
- `REDIS_URL`: Redis caching
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`: LLM providers

### Database Connections
- Neo4j: `bolt://localhost:7687` (default)
- Qdrant: `http://localhost:6333` (default)
- Redis: `redis://localhost:6379` (default)

## File Processing

The system supports multiple file formats:
- **Text**: PDF (with OCR), TXT
- **Images**: JPG, PNG (with captioning and object detection)
- **Audio**: MP3, WAV (with Whisper transcription)
- **Video**: MP4, AVI, MOV (with frame extraction and audio transcription)

All processing includes metadata enrichment, entity extraction, and domain tagging.

## Security Considerations

- Input validation on all file uploads
- Query sanitization and injection prevention
- Role-based access control in `src/security/`
- Audit logging for compliance

## Performance Metrics

The system tracks:
- **Answer Relevancy**: >70% threshold
- **Faithfulness**: >90% threshold
- **Contextual Relevancy**: >70% threshold
- **Latency**: <2000ms target
- **Hallucination Rate**: <10% threshold
- **Cross-modal coherence**: Consistency across different data types

## Common Issues

### Docker Services Not Starting
- Check port conflicts (Neo4j: 7474/7687, Qdrant: 6333/6334, Redis: 6379)
- Ensure Docker is running and has sufficient resources

### Model Downloads
- First run may take time to download models (sentence-transformers, Whisper)
- Models are cached in `models/` directory

### Database Initialization
- Wait 20 seconds after `docker-compose up -d` before running initialization
- Check logs: `docker-compose logs neo4j`, `docker-compose logs qdrant`

## Development Workflow

1. Write test specifications in `tests/specs/`
2. Implement core functionality in appropriate `src/` module
3. Update evaluation metrics if needed
4. Test with `pytest tests/specs/`
5. Run full evaluation suite
6. Update documentation if API changes
