# Implementation Plan: [FEATURE]

**Date**: [DATE] | **Spec**: [link to spec.md]

## Summary

[Primary requirement + technical approach]

## Technical Context

**Backend**: FastAPI, Python 3.11, PostgreSQL, Neo4j, Qdrant, Redis
**Frontend**: Next.js 15, React 18, TypeScript, Tailwind, shadcn/ui
**AI/ML**: OpenAI, Anthropic, sentence-transformers, Whisper, CrewAI
**Testing**: pytest (backend), Jest/Playwright (frontend)

## Project Structure

### Backend Changes
```
backend/src/
├── api/[feature]/
├── services/[feature]/
├── models/[feature].py
└── tests/
```

### Frontend Changes
```
frontend/src/
├── components/[feature]/
├── hooks/use[Feature].ts
└── app/[feature]/page.tsx
```

## Database Design

### PostgreSQL Tables
- [table_name]: [description]

### Neo4j Nodes/Relationships
- [node/relationship]: [description]

## API Design

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/[feature] | [description] |
| POST | /api/v1/[feature] | [description] |

## UI Design

### Pages
- `/[feature]`: [description]

### Components
- `[ComponentName]`: [description]

## Dependencies

- Backend: [new packages]
- Frontend: [new packages]
