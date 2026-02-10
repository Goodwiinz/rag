# Implementation Plan: Evidence Agreement Meter

**Date**: 2025-02-01 | **Spec**: [spec.md](./spec.md)

## Summary

Implement visual evidence agreement meter that classifies source stances on claims and displays consensus level. Backend handles stance classification via LLM with structured output; frontend renders interactive meter with drill-down capability.

## Technical Context

**Backend**: FastAPI, Python 3.11, PostgreSQL, Neo4j, Qdrant, Redis  
**Frontend**: Next.js 15, React 18, TypeScript, Tailwind, shadcn/ui  
**AI/ML**: OpenAI (GPT-4o-mini for stance classification), sentence-transformers  
**Testing**: pytest (backend), Jest/Playwright (frontend)

---

## Technical Approach

### Stance Classification Strategy

Use LLM with structured output for stance detection:
1. Extract claim from user query (or accept explicit claim)
2. For each retrieved source, send (claim, excerpt) pair to LLM
3. LLM returns structured JSON: `{stance, confidence, justification_excerpt}`
4. Aggregate stances into consensus level

**Model Selection**: GPT-4o-mini for cost efficiency at scale. Falls back to GPT-4o for low-confidence classifications.

**Prompt Engineering**: Zero-shot with clear rubric:
- Supporting: Source explicitly or implicitly agrees with claim
- Opposing: Source explicitly or implicitly disagrees with claim
- Neutral: Source discusses topic but takes no position
- Not Addressed: Source doesn't relate to claim

### Parallelization

Classify all sources in parallel (async batch). Redis caches classifications keyed by `(claim_hash, source_id, model_version)` for reproducibility.

---

## Project Structure

### Backend Changes
```
backend/src/
├── api/evidence/
│   ├── __init__.py
│   ├── router.py          # GET /evidence-meter, GET /evidence-breakdown
│   └── schemas.py         # Pydantic models
├── services/evidence/
│   ├── __init__.py
│   ├── stance_classifier.py    # LLM stance detection
│   ├── consensus_calculator.py # Aggregation logic
│   └── cache.py               # Redis caching layer
├── models/evidence.py     # SQLAlchemy models
└── tests/evidence/
    ├── test_stance_classifier.py
    ├── test_consensus_calculator.py
    └── test_api.py
```

### Frontend Changes
```
frontend/src/
├── components/evidence/
│   ├── EvidenceMeter.tsx       # Main meter component
│   ├── EvidenceBreakdown.tsx   # Drill-down panel
│   ├── StanceBadge.tsx         # Supporting/Opposing/Neutral badge
│   └── ConfidenceIndicator.tsx # Confidence warning
├── hooks/
│   └── useEvidenceMeter.ts     # Data fetching hook
└── app/search/
    └── components/
        └── SearchResultCard.tsx  # Integrate meter here
```

---

## Database Design

### PostgreSQL Tables

**stance_classifications**
```sql
CREATE TABLE stance_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_hash VARCHAR(64) NOT NULL,      -- SHA256 of normalized claim
    source_id UUID NOT NULL REFERENCES sources(id),
    stance VARCHAR(20) NOT NULL,          -- supporting/opposing/neutral/not_addressed
    confidence FLOAT NOT NULL,            -- 0.0-1.0
    justification_excerpt TEXT,           -- Excerpt that justifies stance
    model_version VARCHAR(50) NOT NULL,   -- For reproducibility
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(claim_hash, source_id, model_version)
);

CREATE INDEX idx_stance_claim ON stance_classifications(claim_hash);
CREATE INDEX idx_stance_source ON stance_classifications(source_id);
```

### Neo4j Nodes/Relationships

**New Relationship: TAKES_STANCE**
```cypher
(:Source)-[:TAKES_STANCE {
    claim_hash: String,
    stance: String,
    confidence: Float,
    classified_at: DateTime
}]->(:Claim)
```

**New Node: Claim**
```cypher
(:Claim {
    hash: String,        -- SHA256 of normalized text
    text: String,        -- Original claim text
    normalized: String   -- Lowercased, stemmed version
})
```

---

## API Design

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/evidence/meter` | Get consensus meter for a claim |
| GET | `/api/v1/evidence/breakdown` | Get detailed source-by-source stances |
| POST | `/api/v1/evidence/classify` | Classify sources for a claim (internal) |

### GET /api/v1/evidence/meter

**Query Params**:
- `claim`: string (required) - The claim to evaluate
- `source_ids`: string[] (optional) - Limit to specific sources
- `query_id`: string (optional) - Link to search query for context

**Response**:
```json
{
    "claim": "Vitamin D supplementation reduces COVID-19 severity",
    "claim_hash": "abc123...",
    "total_sources": 10,
    "supporting": 7,
    "opposing": 2,
    "neutral": 1,
    "not_addressed": 0,
    "consensus_level": "moderate_agreement",
    "average_confidence": 0.87,
    "retracted_sources": 0,
    "cached": true,
    "reproducibility_hash": "meter_v1_abc123_10src_gpt4omini"
}
```

### GET /api/v1/evidence/breakdown

**Query Params**:
- `claim_hash`: string (required)
- `stance_filter`: string (optional) - Filter by stance type

**Response**:
```json
{
    "claim": "Vitamin D supplementation reduces COVID-19 severity",
    "sources": [
        {
            "source_id": "uuid...",
            "title": "Vitamin D and COVID-19: A Review",
            "stance": "supporting",
            "confidence": 0.92,
            "justification_excerpt": "Our meta-analysis found a 40% reduction in ICU admission...",
            "is_retracted": false
        }
    ]
}
```

---

## UI Design

### Components

**EvidenceMeter** (Primary)
- Horizontal bar with colored segments (green=supporting, red=opposing, gray=neutral)
- Text: "8 of 10 sources agree" or "Mixed evidence (5/3/2)"
- Click to expand breakdown
- Accessibility: aria-label with full text description

**EvidenceBreakdown** (Expandable Panel)
- Three columns: Supporting | Opposing | Neutral
- Each source shows: title, confidence badge, excerpt snippet
- Click source → navigate to source detail

**StanceBadge**
- Color-coded pill: green "Supporting", red "Opposing", gray "Neutral"
- Shows confidence if <85%: "Supporting (72%)"

---

## Caching Strategy

**Redis Keys**:
- `stance:{claim_hash}:{source_id}:{model_version}` → StanceClassification JSON
- `meter:{claim_hash}:{sorted_source_ids_hash}` → EvidenceMeter JSON (TTL: 24h)

**Invalidation**:
- Source content update → delete all stance keys for that source_id
- Model version change → cache miss triggers reclassification

---

## Dependencies

**Backend**:
- None new (uses existing OpenAI, Redis, PostgreSQL)

**Frontend**:
- `framer-motion` (for meter animations)
- Already using shadcn/ui components

---

## Complexity Tracking

### Justified Complexity

1. **Parallel LLM calls**: Necessary for <2s latency with 10+ sources
2. **Dual storage (Postgres + Neo4j)**: Postgres for fast queries, Neo4j for graph traversal in systematic reviews
3. **Confidence-based fallback**: Low confidence → retry with better model. Ensures accuracy.

### Avoided Complexity

1. **Real-time stance updates**: Not implementing WebSocket updates. Polling is sufficient for MVP.
2. **Multi-claim decomposition**: Deferred to v2. Single claim per meter for now.

---

## Constitution Check

| Principle | Compliance |
|-----------|------------|
| Research-First | ✅ Shows source agreement for transparency |
| Deterministic | ✅ Reproducibility hash, cached classifications |
| Citation-Backed | ✅ Every stance linked to excerpt |
| Evaluation-First | ✅ Success criteria SC-001 defines accuracy test |
| Modular | ✅ Separate classifier, calculator, cache services |
